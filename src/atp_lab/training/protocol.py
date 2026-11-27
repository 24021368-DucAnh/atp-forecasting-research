"""Immutable synthetic chronological experiment registration."""
from dataclasses import asdict, dataclass, replace
from datetime import date
import json
import re
import sqlite3

from atp_lab.database.identity import utc_timestamp
from atp_lab.database.schema_v5 import training_transaction
from atp_lab.prediction.commitment import _hash, _id, _json
from atp_lab.prediction.features import FEATURE_NAMES, FEATURE_VERSION
from atp_lab.prediction.temporal import EMBARGO_DAYS

PROTOCOL_VERSION = "S6_SYNTHETIC_PROTOCOL_1"
MAX_EXAMPLES = 4096
_DIGEST = re.compile(r"[0-9a-f]{64}")


def require_digest(value):
    if type(value) is not str or _DIGEST.fullmatch(value) is None:
        raise ValueError("invalid SHA256 digest")
    return value


def canonical_day(value):
    if type(value) is not str:
        raise ValueError("ISO event day required")
    try:
        day = date.fromisoformat(value)
    except ValueError:
        raise ValueError("invalid event day") from None
    if day.isoformat() != value:
        raise ValueError("noncanonical event day")
    return value


def midnight(day):
    return utc_timestamp(canonical_day(day) + "T00:00:00Z")


def fixed_config():
    """Fresh canonical copy of the sole allowed candidate configuration."""
    return {
        "algorithm": "LOGISTIC_MIRRORED_PLATT",
        "version": 1,
        "feature_version": FEATURE_VERSION,
        "feature_names": list(FEATURE_NAMES),
        "signed_feature_count": 10,
        "maturity_days": EMBARGO_DAYS,
        "solver": "lbfgs", "C": 1.0, "max_iter": 2000, "seed": 29,
        "scaler": "fit_mirrored_only",
        "calibration": "disjoint_mirrored_symmetric_probability_logits",
        "probability_clip": 1e-12,
        "thread_limit": 1,
    }


@dataclass(frozen=True)
class TrainingProtocol:
    protocol_id: str
    registered_at: str
    fit_start: str
    fit_end: str
    calibration_start: str
    calibration_end: str
    training_cutoff: str
    evaluation_cohort_id: str
    evaluation_start: str
    evaluation_end: str
    min_fit: int
    min_calibration: int
    min_matched: int

    @property
    def digest(self):
        return _hash(_json(protocol_payload(self)))


def normalize_protocol(protocol: TrainingProtocol) -> TrainingProtocol:
    if type(protocol) is not TrainingProtocol:
        raise ValueError("typed synthetic training protocol required")
    _id(protocol.protocol_id)
    _id(protocol.evaluation_cohort_id)
    for day in (protocol.fit_start, protocol.fit_end, protocol.calibration_start,
                protocol.calibration_end):
        canonical_day(day)
    registered, cutoff, start, end = map(utc_timestamp, (
        protocol.registered_at, protocol.training_cutoff,
        protocol.evaluation_start, protocol.evaluation_end))
    if not (protocol.fit_start < protocol.fit_end <= protocol.calibration_start
            < protocol.calibration_end <= cutoff[:10]
            and registered <= cutoff < start <= end):
        raise ValueError("invalid chronological training or evaluation windows")
    if any(type(n) is not int or not 2 <= n <= MAX_EXAMPLES
           for n in (protocol.min_fit, protocol.min_calibration, protocol.min_matched)):
        raise ValueError("explicit synthetic support minima required")
    return replace(protocol, registered_at=registered, training_cutoff=cutoff,
                   evaluation_start=start, evaluation_end=end)


def protocol_payload(protocol):
    return {"version": PROTOCOL_VERSION, "scope": "SYNTHETIC",
            "protocol": asdict(protocol), "config": fixed_config()}


def decode_protocol(payload):
    try:
        p = normalize_protocol(TrainingProtocol(**payload["protocol"]))
        if payload != protocol_payload(p):
            raise ValueError("protocol payload mismatch")
        return p
    except (KeyError, TypeError, ValueError):
        raise ValueError("invalid immutable training protocol") from None


def _read_protocol(conn, protocol_id):
    _id(protocol_id)
    row = conn.execute(
        "SELECT evaluation_cohort_id,payload,digest FROM training_protocols WHERE protocol_id=?",
        (protocol_id,)).fetchone()
    if row is None:
        raise ValueError("unknown training protocol")
    cohort_id, raw, digest = row
    try:
        p = decode_protocol(json.loads(raw))
        if (p.protocol_id != protocol_id or p.evaluation_cohort_id != cohort_id
                or _json(protocol_payload(p)) != raw or p.digest != digest):
            raise ValueError("protocol digest or identity mismatch")
    except (TypeError, ValueError):
        raise ValueError("invalid immutable training protocol") from None
    return p


def register_protocol(conn: sqlite3.Connection, protocol: TrainingProtocol) -> TrainingProtocol:
    p = normalize_protocol(protocol)
    with training_transaction(conn, write=True):
        existing = conn.execute("SELECT 1 FROM training_protocols WHERE protocol_id=?",
                                (p.protocol_id,)).fetchone()
        if existing is not None:
            if _read_protocol(conn, p.protocol_id) != p:
                raise ValueError("conflicting immutable protocol replay")
            return p
        if conn.execute("SELECT 1 FROM evaluation_cohorts WHERE cohort_id=?",
                        (p.evaluation_cohort_id,)).fetchone():
            raise ValueError("future evaluation cohort already registered")
        if conn.execute("SELECT 1 FROM training_protocols WHERE evaluation_cohort_id=?",
                        (p.evaluation_cohort_id,)).fetchone():
            raise ValueError("future evaluation cohort already reserved")
        conn.execute("INSERT INTO training_protocols VALUES (?,?,?,?)",
                     (p.protocol_id, p.evaluation_cohort_id,
                      _json(protocol_payload(p)), p.digest))
    return p
