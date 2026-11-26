"""Version 3: synthetic forecast provenance, not forecast eligibility."""
from contextlib import closing
import sqlite3

from . import schema_v2
from .migrations import _MARKER, _MARKER_SQL, _objects, _transaction, _version

VERSION = 3

TABLES = (
    """CREATE TABLE feature_snapshots (
        feature_id TEXT PRIMARY KEY NOT NULL CHECK (feature_id GLOB 'SYN-?*'),
        fixture_id TEXT NOT NULL REFERENCES fixture_versions(fixture_id),
        feature_digest TEXT NOT NULL CHECK (length(feature_digest)=64 AND feature_digest NOT GLOB '*[^0-9a-f]*'),
        cutoff TEXT NOT NULL,
        UNIQUE (feature_id, fixture_id)
    )""",
    """CREATE TABLE model_versions (
        model_id TEXT PRIMARY KEY NOT NULL CHECK (model_id GLOB 'SYN-?*'),
        model_digest TEXT NOT NULL CHECK (length(model_digest)=64 AND model_digest NOT GLOB '*[^0-9a-f]*'),
        config_digest TEXT NOT NULL CHECK (length(config_digest)=64 AND config_digest NOT GLOB '*[^0-9a-f]*'),
        training_cutoff TEXT NOT NULL,
        created_at TEXT NOT NULL CHECK (created_at >= training_cutoff),
        scope TEXT NOT NULL CHECK (scope='SYNTHETIC')
    )""",
    """CREATE TABLE predictions (
        prediction_id TEXT PRIMARY KEY NOT NULL CHECK (prediction_id GLOB 'SYN-?*'),
        match_id TEXT NOT NULL REFERENCES matches(match_id),
        fixture_id TEXT NOT NULL REFERENCES fixture_versions(fixture_id),
        feature_id TEXT NOT NULL,
        model_id TEXT NOT NULL REFERENCES model_versions(model_id),
        created_at TEXT NOT NULL,
        probability_a REAL NOT NULL CHECK (typeof(probability_a) IN ('real','integer') AND probability_a BETWEEN 0 AND 1),
        commitment_digest TEXT NOT NULL CHECK (length(commitment_digest)=64 AND commitment_digest NOT GLOB '*[^0-9a-f]*'),
        UNIQUE (fixture_id, model_id),
        FOREIGN KEY (feature_id, fixture_id) REFERENCES feature_snapshots(feature_id, fixture_id)
    )""",
    """CREATE TABLE evaluations (
        evaluation_id TEXT PRIMARY KEY NOT NULL CHECK (evaluation_id GLOB 'SYN-?*'),
        prediction_id TEXT NOT NULL REFERENCES predictions(prediction_id),
        result_id TEXT NOT NULL REFERENCES result_versions(result_id),
        evaluated_at TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('RECORDED','VOID','INELIGIBLE')),
        UNIQUE (prediction_id, result_id)
    )""",
    """CREATE TABLE job_runs (
        job_id TEXT PRIMARY KEY NOT NULL CHECK (job_id GLOB 'SYN-?*'),
        kind TEXT NOT NULL CHECK (kind IN ('INGEST','FEATURES','PREDICT','EVALUATE','TRAIN','BACKUP')),
        attempt INTEGER NOT NULL CHECK (typeof(attempt)='integer' AND attempt > 0),
        started_at TEXT NOT NULL,
        ended_at TEXT NOT NULL CHECK (ended_at >= started_at),
        status TEXT NOT NULL CHECK (status IN ('SUCCEEDED','FAILED','BLOCKED'))
    )""",
    """CREATE TABLE data_quality_issues (
        issue_id TEXT PRIMARY KEY NOT NULL CHECK (issue_id GLOB 'SYN-?*'),
        source_id TEXT NOT NULL REFERENCES data_sources(source_id),
        observed_at TEXT NOT NULL,
        reason TEXT NOT NULL CHECK (length(trim(reason)) > 0)
    )""",
)

IMMUTABLE_TABLES = ("feature_snapshots", "model_versions", "predictions",
                    "evaluations", "job_runs", "data_quality_issues")
TRIGGERS = tuple(
    f"CREATE TRIGGER immutable_{table}_{event.lower()} BEFORE {event} ON {table} "
    f"BEGIN SELECT RAISE(ABORT, 'immutable {table}'); END"
    for table in IMMUTABLE_TABLES
    for event in ("UPDATE", "DELETE")
) + (
    "CREATE TRIGGER prediction_fixture_match BEFORE INSERT ON predictions "
    "WHEN NOT EXISTS (SELECT 1 FROM fixture_versions "
    "WHERE fixture_id=NEW.fixture_id AND match_id=NEW.match_id) "
    "BEGIN SELECT RAISE(ABORT, 'prediction fixture match mismatch'); END",
    "CREATE TRIGGER evaluation_result_match BEFORE INSERT ON evaluations "
    "WHEN NOT EXISTS (SELECT 1 FROM predictions AS p JOIN result_versions AS r "
    "ON r.match_id=p.match_id WHERE p.prediction_id=NEW.prediction_id "
    "AND r.result_id=NEW.result_id) "
    "BEGIN SELECT RAISE(ABORT, 'evaluation result match mismatch'); END",
    "CREATE TRIGGER evaluation_clock BEFORE INSERT ON evaluations "
    "WHEN NEW.evaluated_at < (SELECT created_at FROM predictions WHERE prediction_id=NEW.prediction_id) "
    "OR NEW.evaluated_at < (SELECT observed_at FROM result_versions WHERE result_id=NEW.result_id) "
    "BEGIN SELECT RAISE(ABORT, 'evaluation precedes recorded evidence'); END",
)

DDL = TABLES + TRIGGERS


def _expected_objects() -> list:
    with closing(sqlite3.connect(":memory:")) as reference:
        reference.execute(_MARKER_SQL)
        for statement in schema_v2.DDL + DDL:
            reference.execute(statement)
        return _objects(reference)


def verify_forecast_schema(conn: sqlite3.Connection) -> None:
    """Verify recognized exact forecast/evaluation schema; no writes."""
    if _version(conn) == 4:
        from .schema_v4 import verify_evaluation_schema
        return verify_evaluation_schema(conn)
    if _version(conn) != VERSION or _objects(conn) != _expected_objects():
        raise ValueError("unrecognized forecast schema")
    if conn.execute("SELECT id, marker FROM atp_lab_schema").fetchall() != [(1, _MARKER)]:
        raise ValueError("unrecognized bootstrap marker")
    if conn.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise ValueError("forecast foreign key violation")


def migrate_forecast(conn: sqlite3.Connection) -> int:
    """Upgrade recognized v2 or verify v3 atomically, preserving v2 rows."""
    schema_v2.require_writer(conn)
    with _transaction(conn):
        version = _version(conn)
        if version == schema_v2.VERSION:
            if _objects(conn) != schema_v2._expected_objects():
                raise ValueError("unrecognized identity schema")
            if conn.execute("SELECT id, marker FROM atp_lab_schema").fetchall() != [(1, _MARKER)]:
                raise ValueError("unrecognized bootstrap marker")
            if conn.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise ValueError("identity foreign key violation")
            for statement in DDL:
                conn.execute(statement)
            conn.execute(f"PRAGMA user_version = {VERSION}")
        elif version != VERSION:
            raise ValueError("unsupported forecast migration version")
        verify_forecast_schema(conn)
    return VERSION
