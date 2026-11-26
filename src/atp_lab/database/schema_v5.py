"""Exact additive schema for controlled synthetic training and lifecycle."""
from contextlib import closing, contextmanager
import sqlite3

from . import schema_v2, schema_v3, schema_v4
from .migrations import _MARKER, _MARKER_SQL, _objects, _version

VERSION = 5

TABLES = (
    """CREATE TABLE training_protocols (
        protocol_id TEXT PRIMARY KEY NOT NULL CHECK (protocol_id GLOB 'SYN-?*'),
        evaluation_cohort_id TEXT NOT NULL UNIQUE CHECK (evaluation_cohort_id GLOB 'SYN-?*'),
        payload TEXT NOT NULL CHECK (typeof(payload)='text' AND length(payload)>0),
        digest TEXT NOT NULL CHECK (length(digest)=64 AND digest NOT GLOB '*[^0-9a-f]*')
    )""",
    """CREATE TABLE candidate_artifacts (
        model_id TEXT PRIMARY KEY NOT NULL REFERENCES model_versions(model_id),
        protocol_id TEXT NOT NULL UNIQUE REFERENCES training_protocols(protocol_id),
        payload TEXT NOT NULL CHECK (typeof(payload)='text' AND length(payload)>0)
    )""",
    """CREATE TABLE model_lifecycle_events (
        event_id TEXT PRIMARY KEY NOT NULL CHECK (event_id GLOB 'SYN-?*'),
        sequence INTEGER NOT NULL UNIQUE CHECK (typeof(sequence)='integer' AND sequence>0),
        approval_id TEXT NOT NULL UNIQUE CHECK (approval_id GLOB 'SYN-?*'),
        action TEXT NOT NULL CHECK (action IN ('PROMOTE','ROLLBACK')),
        from_model_id TEXT NOT NULL REFERENCES model_versions(model_id),
        to_model_id TEXT NOT NULL REFERENCES model_versions(model_id),
        decided_at TEXT NOT NULL,
        payload TEXT NOT NULL CHECK (typeof(payload)='text' AND length(payload)>0),
        digest TEXT NOT NULL CHECK (length(digest)=64 AND digest NOT GLOB '*[^0-9a-f]*'),
        CHECK (from_model_id<>to_model_id)
    )""",
)
TRIGGERS = tuple(
    f"CREATE TRIGGER immutable_{table}_{event.lower()} BEFORE {event} ON {table} "
    f"BEGIN SELECT RAISE(ABORT, 'immutable {table}'); END"
    for table in ("training_protocols", "candidate_artifacts", "model_lifecycle_events")
    for event in ("UPDATE", "DELETE")
)
DDL = TABLES + TRIGGERS


def _expected_objects():
    with closing(sqlite3.connect(":memory:")) as reference:
        reference.execute(_MARKER_SQL)
        for statement in schema_v2.DDL + schema_v3.DDL + schema_v4.DDL + DDL:
            reference.execute(statement)
        return _objects(reference)


def verify_training_schema(conn: sqlite3.Connection) -> None:
    if _version(conn) != VERSION or _objects(conn) != _expected_objects():
        raise ValueError("unrecognized training schema")
    if conn.execute("SELECT id, marker FROM atp_lab_schema").fetchall() != [(1, _MARKER)]:
        raise ValueError("unrecognized bootstrap marker")
    if conn.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise ValueError("training foreign key violation")


@contextmanager
def training_transaction(conn: sqlite3.Connection, *, write: bool):
    with schema_v4._owned_transaction(conn, write=write):
        verify_training_schema(conn)
        yield


def migrate_training(conn: sqlite3.Connection) -> int:
    """Upgrade exact v4 to v5 atomically, or verify an existing v5."""
    with schema_v4._owned_transaction(conn, write=True):
        if _version(conn) == schema_v4.VERSION:
            schema_v4.verify_evaluation_schema(conn)
            for statement in DDL:
                conn.execute(statement)
            conn.execute(f"PRAGMA user_version = {VERSION}")
        elif _version(conn) != VERSION:
            raise ValueError("unsupported training migration version")
        verify_training_schema(conn)
    return VERSION
