"""S2 Task 1: actual file-backed SQLite bootstrap contracts."""
from contextlib import closing
import sqlite3

import pytest


def api():
    from atp_lab.database.connection import open_reader, open_writer
    from atp_lab.database.migrations import migrate, apply_migration
    return open_reader, open_writer, migrate, apply_migration


def test_writer_enables_wal_foreign_keys_and_timeout(tmp_path):
    _, writer, _, _ = api()
    with closing(writer(tmp_path / "synthetic.sqlite")) as conn:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000


def test_bootstrap_v1_is_idempotent(tmp_path):
    _, writer, migrate, _ = api()
    path = tmp_path / "synthetic.sqlite"
    with closing(writer(path)) as conn:
        assert migrate(conn) == 1
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
        before = conn.execute("SELECT name, sql FROM sqlite_master ORDER BY name").fetchall()
        assert migrate(conn) == 1
        assert conn.execute("SELECT name, sql FROM sqlite_master ORDER BY name").fetchall() == before
    with closing(writer(path)) as conn:
        assert migrate(conn) == 1


def test_unknown_schema_version_rejected_without_mutation(tmp_path):
    _, writer, migrate, _ = api()
    with closing(writer(tmp_path / "synthetic.sqlite")) as conn:
        conn.execute("PRAGMA user_version = 99")
        with pytest.raises(ValueError):
            migrate(conn)
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 99
        assert conn.execute("SELECT name FROM sqlite_master").fetchall() == []


def test_unrecognized_nonempty_v0_rejected(tmp_path):
    _, writer, migrate, _ = api()
    with closing(writer(tmp_path / "synthetic.sqlite")) as conn:
        conn.execute("CREATE TABLE unrelated (id INTEGER PRIMARY KEY)")
        conn.execute("INSERT INTO unrelated VALUES (7)")
        conn.commit()
        with pytest.raises(ValueError):
            migrate(conn)
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 0
        assert conn.execute("SELECT id FROM unrelated").fetchall() == [(7,)]


def test_reader_is_read_only_and_does_not_create_missing_database(tmp_path):
    reader, writer, migrate, _ = api()
    path = tmp_path / "synthetic.sqlite"
    with pytest.raises(sqlite3.OperationalError):
        reader(path)
    assert not path.exists()
    with closing(writer(path)) as conn:
        migrate(conn)
    with closing(reader(path)) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn.execute("PRAGMA query_only").fetchone()[0] == 1
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("CREATE TABLE forbidden (id INTEGER)")
        conn.execute("PRAGMA query_only = OFF")
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("CREATE TABLE still_forbidden (id INTEGER)")


def test_failed_migration_rolls_back_schema_and_version(tmp_path):
    _, writer, _, apply = api()
    with closing(writer(tmp_path / "synthetic.sqlite")) as conn:
        with pytest.raises(sqlite3.OperationalError):
            apply(conn, 0, 1, (
                "CREATE TABLE temporary_record (id INTEGER PRIMARY KEY)",
                "INSERT INTO missing_table VALUES (1)",
            ))
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 0
        assert conn.execute("SELECT name FROM sqlite_master").fetchall() == []
        assert not conn.in_transaction


def test_migration_does_not_commit_caller_transaction(tmp_path):
    _, writer, migrate, _ = api()
    with closing(writer(tmp_path / "synthetic.sqlite")) as conn:
        conn.execute("BEGIN IMMEDIATE")
        with pytest.raises(ValueError):
            migrate(conn)
        assert conn.in_transaction
        conn.rollback()
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 0


def test_reader_path_with_uri_special_characters(tmp_path):
    reader, writer, migrate, _ = api()
    path = tmp_path / "synthetic # percent %.sqlite"
    with closing(writer(path)) as conn:
        migrate(conn)
    with closing(reader(path)) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
