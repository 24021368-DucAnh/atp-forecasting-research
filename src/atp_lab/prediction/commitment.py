"""Atomic offline synthetic commitment; never accepts a caller forecast."""
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math
import sqlite3

from atp_lab.database import forecast
from atp_lab.database.identity import _ID, utc_timestamp
from atp_lab.database.schema_v4 import evaluation_transaction
from . import inference
from .features import FEATURE_NAMES, FEATURE_VERSION

VERSION = "S5_SYNTHETIC_COMMITMENT_1"
SCOPE = "SYNTHETIC_PROSPECTIVE"


class UnverifiedCommitment(ValueError):
    """No S5 evidence receipt; legacy storage alone is not certification."""


@dataclass(frozen=True)
class Commitment:
    prediction: forecast.Prediction
    feature: forecast.FeatureSnapshot
    receipt_json: str


def _id(value):
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise ValueError("invalid synthetic identity")
    return value


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False)


def _hash(payload: str):
    return sha256(payload.encode("utf-8")).hexdigest()


def _stable_id(kind, *values):
    return "SYN-" + kind + "-" + _hash(_json(values))


def _feature_id(fixture_id, cutoff, digest):
    return _stable_id("feature", VERSION, FEATURE_VERSION, fixture_id, cutoff, digest)


def _prediction_id(fixture_id, model_id):
    return _stable_id("prediction", VERSION, fixture_id, model_id)


def _require_new_target(conn, fixture_id, match_id):
    """Reject retroactive new evidence even when later clocks are claimed."""
    row = conn.execute(
        "SELECT source_id,revision FROM fixture_versions WHERE fixture_id=? AND match_id=?",
        (fixture_id, match_id)).fetchone()
    if row is None:
        raise ValueError("unknown fixture identity")
    if conn.execute("SELECT 1 FROM result_versions WHERE match_id=? LIMIT 1",
                    (match_id,)).fetchone():
        raise ValueError("target already has a persisted result")
    if conn.execute(
        "SELECT 1 FROM fixture_versions WHERE match_id=? "
        "AND (source_id<>? OR revision>?) LIMIT 1",
        (match_id, row[0], row[1])).fetchone():
        raise ValueError("target already superseded or ambiguous")


def _get_commitment(conn, prediction_id):
    _id(prediction_id)
    p = conn.execute(
        "SELECT prediction_id,match_id,fixture_id,feature_id,model_id,created_at,"
        "probability_a,commitment_digest FROM predictions WHERE prediction_id=?",
        (prediction_id,)).fetchone()
    r = conn.execute("SELECT payload FROM prediction_receipts WHERE prediction_id=?",
                     (prediction_id,)).fetchone()
    if p is None or r is None:
        raise UnverifiedCommitment("no S5 commitment receipt")
    prediction = forecast.Prediction(*p)
    row = conn.execute(
        "SELECT feature_id,fixture_id,feature_digest,cutoff FROM feature_snapshots "
        "WHERE feature_id=?", (prediction.feature_id,)).fetchone()
    model_row = conn.execute(
        "SELECT model_id,model_digest,config_digest,training_cutoff,created_at,scope "
        "FROM model_versions WHERE model_id=?", (prediction.model_id,)).fetchone()
    if row is None or model_row is None:
        raise ValueError("broken commitment lineage")
    feature = forecast.FeatureSnapshot(*row)
    model = forecast.ModelVersion(*model_row)
    raw = r[0]
    try:
        payload = json.loads(raw)
        features = payload["features"]
        values = features["values"]
        result_ids = features["result_ids"]
        events = payload["events"]
        if (
            type(payload) is not dict or _json(payload) != raw
            or _hash(raw) != prediction.commitment_digest
            or payload["version"] != VERSION or payload["scope"] != SCOPE
            or payload["feature_version"] != FEATURE_VERSION
            or payload["prediction_id"] != prediction.prediction_id
            or payload["feature_id"] != prediction.feature_id
            or payload["fixture_id"] != prediction.fixture_id
            or payload["match_id"] != prediction.match_id
            or payload["model"] != asdict(model)
            or model != inference.synthetic_model_version(created_at=model.created_at)
            or payload["created_at"] != prediction.created_at
            or utc_timestamp(prediction.created_at) != prediction.created_at
            or feature.cutoff != prediction.created_at
            or model.created_at > feature.cutoff
            or feature.fixture_id != prediction.fixture_id
            or feature.feature_id != _feature_id(feature.fixture_id, feature.cutoff, feature.feature_digest)
            or prediction.prediction_id != _prediction_id(prediction.fixture_id, prediction.model_id)
            or features["fixture_id"] != feature.fixture_id
            or features["cutoff"] != feature.cutoff
            or features["digest"] != feature.feature_digest
            or type(values) is not list
            or tuple(x[0] for x in values) != FEATURE_NAMES
            or any(type(x) is not list or len(x) != 2 or
                   type(x[1]) not in (int, float) or not math.isfinite(x[1])
                   for x in values)
            or type(result_ids) is not list or len(set(result_ids)) != len(result_ids)
            or any(_id(x) != x for x in result_ids)
            or type(events) is not list or not events
            or type(payload["probability_a"]) not in (int, float)
            or payload["probability_a"] != prediction.probability_a
            or prediction.probability_a != inference._elo_p(dict(values)["overall_elo_diff"], 0.)
        ):
            raise ValueError("commitment receipt mismatch")
        evidence = {
            "version": "S4_SYNTHETIC_INFERENCE_1",
            "match_id": prediction.match_id, "fixture_id": prediction.fixture_id,
            "model": asdict(model), "feature_digest": feature.feature_digest,
            "cutoff": feature.cutoff, "probability_a": prediction.probability_a,
            "events": events,
        }
        if payload["preview_digest"] != inference._digest(evidence):
            raise ValueError("preview digest mismatch")
    except (KeyError, TypeError, IndexError, ValueError, OverflowError):
        raise ValueError("invalid S5 commitment receipt") from None
    return Commitment(prediction, feature, raw)


def get_commitment(conn: sqlite3.Connection, prediction_id: str) -> Commitment:
    """Read one verified immutable receipt without writing."""
    with evaluation_transaction(conn, write=False):
        return _get_commitment(conn, prediction_id)


def commit_prediction(conn: sqlite3.Connection, fixture_id: str, event_metadata,
                      *, cutoff: str, created_at: str,
                      model_id: str = inference.MODEL_ID) -> Commitment:
    """Recompute S4 under the same writer lock as all three durable inserts.

    S5 v1 requires equal normalized cutoff and commit clocks. These are
    synthetic claims, not independently authenticated timestamps.
    """
    limit, created = utc_timestamp(cutoff), utc_timestamp(created_at)
    if limit != created or model_id != inference.MODEL_ID:
        raise ValueError("equal clocks and fixed synthetic baseline required")
    with evaluation_transaction(conn, write=True):
        preview, evidence = inference._predict_in_transaction(
            conn, fixture_id, event_metadata, cutoff=limit)
        fid = _feature_id(preview.fixture_id, limit, preview.features.digest)
        pid = _prediction_id(preview.fixture_id, preview.model.model_id)
        feature = forecast.FeatureSnapshot(fid, preview.fixture_id, preview.features.digest, limit)
        raw = _json({
            "version": VERSION, "scope": SCOPE, "feature_version": FEATURE_VERSION,
            "prediction_id": pid, "feature_id": fid, "fixture_id": preview.fixture_id,
            "match_id": preview.match_id, "model": asdict(preview.model),
            "features": asdict(preview.features), "events": evidence["events"],
            "preview_digest": preview.digest, "created_at": created,
            "probability_a": preview.probability_a,
        })
        prediction = forecast.Prediction(
            pid, preview.match_id, preview.fixture_id, fid, preview.model.model_id,
            created, preview.probability_a, _hash(raw))
        candidate = Commitment(prediction, feature, raw)
        existing = conn.execute(
            "SELECT prediction_id FROM predictions WHERE fixture_id=? AND model_id=?",
            (preview.fixture_id, model_id)).fetchone()
        if existing is not None:
            if _get_commitment(conn, existing[0]) != candidate:
                raise ValueError("conflicting immutable commitment replay")
            return candidate
        _require_new_target(conn, preview.fixture_id, preview.match_id)
        forecast.append_feature(conn, feature)
        forecast.append_prediction(conn, prediction)
        conn.execute("INSERT INTO prediction_receipts(prediction_id,payload) VALUES (?,?)",
                     (pid, raw))
        return candidate
