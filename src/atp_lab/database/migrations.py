"""Transactional bootstrap for the unreleased local S2 database."""
from contextlib import contextmanager
import sqlite3

SCHEMA_VERSION = 1
_MARKER_SQL = "CREATE TABLE atp_lab_schema (id INTEGER PRIMARY KEY CHECK (id = 1), marker TEXT NOT NULL CHECK (marker = 'S2_BOOTSTRAP_V1'))"
_MARKER = "S2_BOOTSTRAP_V1"


@contextmanager
def _transaction(conn: sqlite3.Connection):
    if conn.in_transaction:
        raise ValueError("migration requires an idle connection")
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield
        conn.commit()
    except BaseException:
        conn.rollback()
        raise


def _version(conn: sqlite3.Connection) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]


def _objects(conn: sqlite3.Connection) -> list:
    return conn.execute(
        "SELECT type, name, sql FROM sqlite_master ORDER BY name"
    ).fetchall()


def apply_migration(conn: sqlite3.Connection, expected_version: int,
                    target_version: int, statements: tuple[str, ...]) -> int:
    """Apply trusted internal DDL/DML atomically; never use untrusted SQL.

    Statements must not contain transaction control, PRAGMAs or SQL that
    modifies migration metadata. Execute each separately, not executescript.
    """
    if (type(expected_version) is not int or type(target_version) is not int
            or expected_version < 0 or target_version != expected_version + 1
            or target_version > 2147483647):
        raise ValueError("invalid migration version step")
    with _transaction(conn):
        if _version(conn) != expected_version:
            raise ValueError("unexpected migration version")
        for statement in statements:
            conn.execute(statement)
        conn.execute(f"PRAGMA user_version = {target_version}")
    return target_version


def migrate(conn: sqlite3.Connection) -> int:
    """Initialize or recognize the exact bootstrap-only schema."""
    with _transaction(conn):
        version = _version(conn)
        objects = _objects(conn)
        if version == 0:
            if objects:
                raise ValueError("unrecognized nonempty version-0 database")
            conn.execute(_MARKER_SQL)
            conn.execute("INSERT INTO atp_lab_schema VALUES (1, ?)", (_MARKER,))
            conn.execute("PRAGMA user_version = 1")
        elif version == SCHEMA_VERSION:
            if objects != [("table", "atp_lab_schema", _MARKER_SQL)]:
                raise ValueError("unrecognized bootstrap schema")
            if conn.execute("SELECT id, marker FROM atp_lab_schema").fetchall() != [(1, _MARKER)]:
                raise ValueError("unrecognized bootstrap marker")
        else:
            raise ValueError("unsupported database schema version")
    return SCHEMA_VERSION
