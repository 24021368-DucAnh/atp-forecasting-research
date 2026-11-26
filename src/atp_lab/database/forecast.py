"""Immutable synthetic forecast storage; no fitting, inference or scoring."""
from dataclasses import dataclass, fields
import re
import sqlite3

from .identity import _ID, utc_timestamp
from .schema_v2 import require_writer
from .schema_v3 import VERSION, migrate_forecast

_DIGEST = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class FeatureSnapshot:
    feature_id: str
    fixture_id: str
    feature_digest: str
    cutoff: str


@dataclass(frozen=True)
class ModelVersion:
    model_id: str
    model_digest: str
    config_digest: str
    training_cutoff: str
    created_at: str
    scope: str


@dataclass(frozen=True)
class Prediction:
    prediction_id: str
    match_id: str
    fixture_id: str
    feature_id: str
    model_id: str
    created_at: str
    probability_a: float
    commitment_digest: str


@dataclass(frozen=True)
class Evaluation:
    evaluation_id: str
    prediction_id: str
    result_id: str
    evaluated_at: str
    status: str


@dataclass(frozen=True)
class JobRun:
    job_id: str
    kind: str
    attempt: int
    started_at: str
    ended_at: str
    status: str


@dataclass(frozen=True)
class QualityIssue:
    issue_id: str
    source_id: str
    observed_at: str
    reason: str


_TABLES = {
    FeatureSnapshot: "feature_snapshots",
    ModelVersion: "model_versions",
    Prediction: "predictions",
    Evaluation: "evaluations",
    JobRun: "job_runs",
    QualityIssue: "data_quality_issues",
}
_CLOCKS = {"cutoff", "training_cutoff", "created_at", "evaluated_at",
           "started_at", "ended_at", "observed_at"}


def _canonical(name: str, value):
    if name in _CLOCKS:
        return utc_timestamp(value)
    if name == "probability_a":
        if type(value) not in (int, float) or not 0 <= value <= 1:
            raise ValueError("probability must be a finite real number in [0,1]")
        return float(value)
    if name == "attempt":
        if type(value) is not int or not 1 <= value <= 9223372036854775807:
            raise ValueError("attempt must be a positive SQLite integer")
        return value
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise ValueError(f"invalid {name}")
    if name.endswith("_id") and _ID.fullmatch(value) is None:
        raise ValueError(f"non-synthetic or invalid {name}")
    if name.endswith("_digest") and _DIGEST.fullmatch(value) is None:
        raise ValueError(f"invalid {name}")
    return value


def _insert(conn: sqlite3.Connection, record, record_type: type) -> bool:
    if type(record) is not record_type:
        raise ValueError("incorrect record type")
    require_writer(conn)
    if not conn.in_transaction:
        raise ValueError("explicit caller transaction required")
    if conn.execute("PRAGMA user_version").fetchone()[0] not in (VERSION, 4):
        raise ValueError("forecast schema v3 or v4 required")
    table = _TABLES[record_type]
    values = {field.name: _canonical(field.name, getattr(record, field.name))
              for field in fields(record_type)}
    names = ", ".join(values)
    key = next(iter(values))
    payload = tuple(values.values())
    existing = conn.execute(f"SELECT {names} FROM {table} WHERE {key} = ?",
                            (values[key],)).fetchone()
    if existing is not None:
        if tuple(existing) != payload:
            raise ValueError("conflicting immutable record replay")
        return False
    placeholders = ", ".join("?" for _ in values)
    conn.execute(f"INSERT INTO {table} ({names}) VALUES ({placeholders})", payload)
    return True


def append_feature(conn: sqlite3.Connection, record: FeatureSnapshot) -> bool:
    return _insert(conn, record, FeatureSnapshot)


def append_model(conn: sqlite3.Connection, record: ModelVersion) -> bool:
    return _insert(conn, record, ModelVersion)


def append_prediction(conn: sqlite3.Connection, record: Prediction) -> bool:
    return _insert(conn, record, Prediction)


def append_evaluation(conn: sqlite3.Connection, record: Evaluation) -> bool:
    return _insert(conn, record, Evaluation)


def record_job(conn: sqlite3.Connection, record: JobRun) -> bool:
    return _insert(conn, record, JobRun)


def record_quality_issue(conn: sqlite3.Connection, record: QualityIssue) -> bool:
    return _insert(conn, record, QualityIssue)


def list_prediction_history(conn: sqlite3.Connection, match_id: str) -> list[dict]:
    """Return exact stored revisions using one read snapshot, with no writes."""
    match_id = _canonical("match_id", match_id)
    if conn.execute("PRAGMA user_version").fetchone()[0] not in (VERSION, 4):
        raise ValueError("forecast schema v3 or v4 required")
    p_fields = tuple(field.name for field in fields(Prediction))
    e_fields = tuple(field.name for field in fields(Evaluation))
    columns = ", ".join([f"p.{name}" for name in p_fields] +
                        [f"e.{name}" for name in e_fields])
    rows = conn.execute(
        f"SELECT {columns} FROM predictions AS p "
        "LEFT JOIN evaluations AS e ON e.prediction_id=p.prediction_id "
        "WHERE p.match_id=? ORDER BY p.created_at, p.prediction_id, "
        "e.evaluated_at, e.evaluation_id", (match_id,))
    history = {}
    for row in rows:
        row = tuple(row)
        if row[0] not in history:
            history[row[0]] = dict(zip(p_fields, row[:len(p_fields)]))
            history[row[0]]["evaluations"] = []
        assessment = row[len(p_fields):]
        if assessment[0] is not None:
            history[row[0]]["evaluations"].append(dict(zip(e_fields, assessment)))
    return list(history.values())
