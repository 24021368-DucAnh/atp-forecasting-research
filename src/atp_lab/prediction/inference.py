"""Read-only point-in-time synthetic Elo inference, not a forecast commit."""
from dataclasses import asdict, dataclass, replace
from datetime import date
from hashlib import sha256
import json
import re
import sqlite3

from atp_lab.database.forecast import ModelVersion
from atp_lab.database.identity import utc_timestamp
from atp_lab.database.schema_v3 import verify_forecast_schema
from .features import (FEATURE_VERSION, FeatureSnapshot,
                       _elo_p, build_feature_snapshot)
from .temporal import (HistoricalResult, UpcomingFixture, TemporalError,
                       normalize_fixture)

MODEL_ID = "SYN-global-elo-v1"
MAX_ROWS = 100000
_SYN_ID = re.compile(r"SYN-[A-Za-z0-9._:-]+")


class InferenceError(ValueError):
    """Synthetic preview is not eligible."""


@dataclass(frozen=True)
class EventMetadata:
    tournament_id: str
    revision: int
    event_start: date
    observed_at: str
    available_at: str | None


@dataclass(frozen=True)
class InferencePreview:
    match_id: str
    fixture_id: str
    model: ModelVersion
    features: FeatureSnapshot
    probability_a: float
    digest: str


def _digest(data) -> str:
    return sha256(json.dumps(data, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=True, allow_nan=False).encode("utf-8")).hexdigest()


def _clock(value):
    try:
        return utc_timestamp(value)
    except (TypeError, ValueError):
        raise InferenceError("invalid clock") from None


def _id(value):
    if type(value) is not str or _SYN_ID.fullmatch(value) is None:
        raise InferenceError("invalid synthetic identity")
    return value


def synthetic_model_version(*, created_at: str) -> ModelVersion:
    """Fixed no-fit baseline; creation time doubles as cutoff convention."""
    clock = _clock(created_at)
    return ModelVersion(
        MODEL_ID,
        _digest({"algorithm": "GLOBAL_ELO_NO_FIT", "version": 1,
                 "probability": "1/(1+10**(-clip(diff/400,-15,15)))",
                 "probability_clip": [1e-12, 1-1e-12]}),
        _digest({"feature_version": FEATURE_VERSION, "rating_initial": 1500,
                 "k": 24, "event_embargo_days": 28,
                 "feature": "overall_elo_diff"}),
        clock, clock, "SYNTHETIC")


def _model(conn, cutoff):
    row = conn.execute(
        "SELECT model_id,model_digest,config_digest,training_cutoff,created_at,scope "
        "FROM model_versions WHERE model_id=?", (MODEL_ID,)).fetchone()
    if row is None:
        raise InferenceError("fixed synthetic model not registered")
    model = ModelVersion(*row)
    if model != synthetic_model_version(created_at=model.created_at) or model.created_at > cutoff:
        raise InferenceError("model digest or cutoff mismatch")
    return model


def _event_inventory(items, cutoff):
    if type(items) not in (tuple, list) or len(items) > MAX_ROWS:
        raise InferenceError("invalid event metadata inventory")
    latest = {}
    seen = set()
    for item in items:
        if type(item) is not EventMetadata:
            raise InferenceError("invalid event metadata type")
        _id(item.tournament_id)
        if (type(item.event_start) is not date or type(item.revision) is not int
                or not 1 <= item.revision <= 9223372036854775807):
            raise InferenceError("invalid event metadata revision")
        observed = _clock(item.observed_at)
        available = None if item.available_at is None else _clock(item.available_at)
        if available is not None and available < observed:
            raise InferenceError("invalid event metadata clock order")
        if observed > cutoff:
            continue
        key = (item.tournament_id, item.revision)
        if key in seen:
            raise InferenceError("duplicate visible event metadata revision")
        seen.add(key)
        row = replace(item, observed_at=observed, available_at=available)
        previous = latest.get(item.tournament_id)
        if previous is None or row.revision > previous.revision:
            latest[item.tournament_id] = row
    return latest


def _event(events, tournament_id, cutoff):
    row = events.get(tournament_id)
    if row is None or row.available_at is None or row.available_at > cutoff:
        raise InferenceError("event metadata unavailable at cutoff")
    return row


def _bounded(cursor):
    rows = cursor.fetchmany(MAX_ROWS + 1)
    if len(rows) > MAX_ROWS:
        raise InferenceError("synthetic inventory exceeds bounded preview")
    return rows


def _source(mode, permission):
    if (mode, permission) != ("SYNTHETIC", "LOCKED"):
        raise InferenceError("source scope mismatch")


def _fixture(conn, fixture_id, events, cutoff):
    match = conn.execute("SELECT match_id FROM fixture_versions WHERE fixture_id=?",
                         (fixture_id,)).fetchone()
    if match is None:
        raise InferenceError("fixture not found")
    rows = _bounded(conn.execute(
        "SELECT f.fixture_id,f.match_id,f.source_id,f.revision,m.tournament_id,"
        "t.surface,f.player_a,f.player_b,f.observed_at,f.available_at,"
        "f.scheduled_start,f.state,m.canonical_a,m.canonical_b,s.mode,s.permission_status "
        "FROM fixture_versions f JOIN matches m ON m.match_id=f.match_id "
        "JOIN tournaments t ON t.tournament_id=m.tournament_id "
        "JOIN data_sources s ON s.source_id=f.source_id "
        "WHERE f.match_id=? AND f.observed_at<=? ORDER BY f.revision DESC",
        (match[0], cutoff)))
    if not rows or len({row[2] for row in rows}) != 1 or rows[0][0] != fixture_id:
        raise InferenceError("stale or ambiguous fixture")
    row = rows[0]
    _source(row[14], row[15])
    if tuple(row[6:8]) != tuple(row[12:14]):
        raise InferenceError("fixture participant mismatch")
    event = _event(events, row[4], cutoff)
    target = UpcomingFixture(*row[:5], event.event_start, *row[5:12])
    return normalize_fixture(target, cutoff=cutoff)


def _history(conn, target, events, cutoff):
    if conn.execute("SELECT 1 FROM result_versions WHERE match_id=? "
                    "AND observed_at<=? LIMIT 1",
                    (target.match_id, cutoff)).fetchone():
        raise InferenceError("target already has observed result")
    rows = _bounded(conn.execute(
        "SELECT r.result_id,r.match_id,r.source_id,r.revision,m.tournament_id,"
        "t.surface,m.canonical_a,m.canonical_b,r.observed_at,r.available_at,"
        "r.published_at,r.actual_start,r.state,r.winner,s.mode,s.permission_status "
        "FROM result_versions r JOIN matches m ON m.match_id=r.match_id "
        "JOIN tournaments t ON t.tournament_id=m.tournament_id "
        "JOIN data_sources s ON s.source_id=r.source_id "
        "WHERE r.observed_at<=?", (cutoff,)))
    history = []
    for row in rows:
        _source(row[14], row[15])
        event = _event(events, row[4], cutoff)
        history.append(HistoricalResult(*row[:5], event.event_start, *row[5:14]))
    return tuple(history)


def _metadata_payload(row):
    payload = asdict(row)
    payload["event_start"] = row.event_start.isoformat()
    return payload


def _predict_in_transaction(conn: sqlite3.Connection, fixture_id: str,
                            event_metadata: tuple[EventMetadata, ...] | list[EventMetadata],
                            *, cutoff: str):
    """Shared verified snapshot computation; never opens/closes caller transaction."""
    if not conn.in_transaction:
        raise InferenceError("active snapshot required")
    limit = _clock(cutoff)
    _id(fixture_id)
    try:
        verify_forecast_schema(conn)
        events = _event_inventory(event_metadata, limit)
        target = _fixture(conn, fixture_id, events, limit)
        history = _history(conn, target, events, limit)
        model = _model(conn, limit)
        features = build_feature_snapshot(target, history, cutoff=limit)
        probability = _elo_p(dict(features.values)["overall_elo_diff"], 0.)
        selected_ids = set(features.result_ids)
        event_ids = {target.tournament_id}
        event_ids.update(row.tournament_id for row in history if row.result_id in selected_ids)
        evidence = {
            "version": "S4_SYNTHETIC_INFERENCE_1",
            "match_id": target.match_id, "fixture_id": target.fixture_id,
            "model": asdict(model), "feature_digest": features.digest,
            "cutoff": limit, "probability_a": probability,
            "events": [_metadata_payload(events[key]) for key in sorted(event_ids)],
        }
        preview = InferencePreview(target.match_id, target.fixture_id, model,
                                   features, probability, _digest(evidence))
        return preview, evidence
    except TemporalError as exc:
        raise InferenceError(str(exc)) from None


def predict_fixture(conn: sqlite3.Connection, fixture_id: str,
                    event_metadata: tuple[EventMetadata, ...] | list[EventMetadata],
                    *, cutoff: str) -> InferencePreview:
    """Compute an immutable preview in one verified read snapshot.

    Requires complete synthetic event/fixture/result revision inventories.
    The fixed model is not fitted; clocks and metadata are caller claims.
    No prediction or feature row is committed here.
    """
    if conn.in_transaction:
        raise InferenceError("idle connection required")
    conn.execute("BEGIN")
    try:
        preview, _ = _predict_in_transaction(conn, fixture_id, event_metadata, cutoff=cutoff)
        return preview
    finally:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
