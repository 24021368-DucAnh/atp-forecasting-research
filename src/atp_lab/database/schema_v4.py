"""Additive synthetic S5 evidence schema; legacy v3 rows are not certified."""
from contextlib import closing, contextmanager
import sqlite3

from . import schema_v2, schema_v3
from .migrations import _MARKER, _MARKER_SQL, _objects, _version

VERSION = 4

TABLES = (
    """CREATE TABLE prediction_receipts (
        prediction_id TEXT PRIMARY KEY NOT NULL REFERENCES predictions(prediction_id),
        payload TEXT NOT NULL CHECK (typeof(payload)='text' AND length(payload)>0)
    )""",
    """CREATE TABLE assessment_receipts (
        evaluation_id TEXT PRIMARY KEY NOT NULL REFERENCES evaluations(evaluation_id),
        reason TEXT NOT NULL CHECK (length(trim(reason))>0),
        outcome_a INTEGER CHECK (outcome_a IS NULL OR
            (typeof(outcome_a)='integer' AND outcome_a IN (0,1)))
    )""",
    """CREATE TABLE evaluation_cohorts (
        cohort_id TEXT PRIMARY KEY NOT NULL CHECK (cohort_id GLOB 'SYN-?*'),
        registered_at TEXT NOT NULL,
        cutoff_end TEXT NOT NULL CHECK (cutoff_end>=registered_at),
        payload TEXT NOT NULL CHECK (typeof(payload)='text' AND length(payload)>0),
        digest TEXT NOT NULL CHECK (length(digest)=64 AND digest NOT GLOB '*[^0-9a-f]*')
    )""",
)

TRIGGERS = tuple(
    f"CREATE TRIGGER immutable_{table}_{event.lower()} BEFORE {event} ON {table} "
    f"BEGIN SELECT RAISE(ABORT, 'immutable {table}'); END"
    for table in ("prediction_receipts", "assessment_receipts", "evaluation_cohorts")
    for event in ("UPDATE", "DELETE")
) + (
    "CREATE TRIGGER assessment_receipt_status BEFORE INSERT ON assessment_receipts "
    "WHEN NOT EXISTS (SELECT 1 FROM evaluations e WHERE e.evaluation_id=NEW.evaluation_id "
    "AND ((e.status='RECORDED' AND NEW.reason='ELIGIBLE' AND NEW.outcome_a IS NOT NULL) "
    "OR (e.status<>'RECORDED' AND NEW.reason<>'ELIGIBLE' AND NEW.outcome_a IS NULL))) "
    "BEGIN SELECT RAISE(ABORT, 'assessment receipt status mismatch'); END",
)
DDL = TABLES + TRIGGERS


def _expected_objects():
    with closing(sqlite3.connect(":memory:")) as reference:
        reference.execute(_MARKER_SQL)
        for statement in schema_v2.DDL + schema_v3.DDL + DDL:
            reference.execute(statement)
        return _objects(reference)


def verify_evaluation_schema(conn: sqlite3.Connection) -> None:
    if _version(conn) == 5:
        from .schema_v5 import verify_training_schema
        return verify_training_schema(conn)
    if _version(conn) != VERSION or _objects(conn) != _expected_objects():
        raise ValueError("unrecognized evaluation schema")
    if conn.execute("SELECT id, marker FROM atp_lab_schema").fetchall() != [(1, _MARKER)]:
        raise ValueError("unrecognized bootstrap marker")
    if conn.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise ValueError("evaluation foreign key violation")


@contextmanager
def _owned_transaction(conn: sqlite3.Connection, *, write: bool):
    if conn.in_transaction:
        raise ValueError("evaluation requires an idle connection")
    if write:
        schema_v2.require_writer(conn)
    conn.execute("BEGIN IMMEDIATE" if write else "BEGIN")
    try:
        yield
        conn.execute("COMMIT" if write else "ROLLBACK")
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise


@contextmanager
def evaluation_transaction(conn: sqlite3.Connection, *, write: bool):
    """One verified owned snapshot/transaction; never consumes caller work."""
    with _owned_transaction(conn, write=write):
        verify_evaluation_schema(conn)
        yield


def migrate_evaluation(conn: sqlite3.Connection) -> int:
    """Upgrade exact v3 to v4 atomically, or verify an existing v4."""
    with _owned_transaction(conn, write=True):
        if _version(conn) == schema_v3.VERSION:
            schema_v3.verify_forecast_schema(conn)
            for statement in DDL:
                conn.execute(statement)
            conn.execute(f"PRAGMA user_version = {VERSION}")
        elif _version(conn) != VERSION:
            raise ValueError("unsupported evaluation migration version")
        verify_evaluation_schema(conn)
    return VERSION
