"""S2.2: real SQLite, synthetic identity and immutable revisions."""
from contextlib import closing
from dataclasses import replace
import sqlite3

import pytest

from atp_lab.database.connection import open_writer
from atp_lab.database.migrations import migrate

OBS = "2026-01-01T08:00:00Z"
READY = "2026-01-01T08:05:00Z"
START = "2026-01-02T10:00:00Z"
DONE = "2026-01-02T12:00:00Z"
LATER = "2026-01-02T12:05:00Z"


def api():
    from atp_lab.database import identity
    return identity


@pytest.fixture
def conn(tmp_path):
    with closing(open_writer(tmp_path / "identity.sqlite")) as db:
        migrate(db)
        yield db


def seed(db):
    a = api()
    a.migrate_identity(db)
    db.execute("BEGIN IMMEDIATE")
    a.put_source(db, a.Source("SYN-feed", "SYNTHETIC", "LOCKED"))
    a.put_source(db, a.Source("SYN-other", "SYNTHETIC", "LOCKED"))
    a.put_snapshot(db, a.Snapshot("SYN-s1", "SYN-feed", "a" * 64, OBS))
    a.put_snapshot(db, a.Snapshot("SYN-s2", "SYN-feed", "b" * 64, LATER))
    a.put_snapshot(db, a.Snapshot("SYN-other-s", "SYN-other", "c" * 64, OBS))
    for player in ("SYN-A", "SYN-B", "SYN-C"):
        a.put_player(db, a.Player(player))
    a.put_alias(db, a.PlayerAlias("SYN-feed", "p1", "SYN-A"))
    a.put_tournament(db, a.Tournament("SYN-t1", "SYN-event", "2026", "ATP250", "HARD"))
    a.put_match(db, a.Match("SYN-m1", "SYN-t1", "SYN-A", "SYN-B"))
    a.put_match_alias(db, a.MatchAlias("SYN-feed", "m1", "SYN-m1"))
    db.commit()
    return a


def fixture(a, **kwargs):
    record = a.Fixture("SYN-f1", "SYN-m1", 1, "SYN-feed", "SYN-s1",
                       "SYN-A", "SYN-B", OBS, READY, START, "SCHEDULED")
    return replace(record, **kwargs)


def result(a, **kwargs):
    record = a.Result("SYN-r1", "SYN-m1", 1, "SYN-feed", "SYN-s2",
                      LATER, LATER, DONE, START, "COMPLETED", "SYN-A")
    return replace(record, **kwargs)


def test_explicit_v1_upgrade_and_idempotence(conn):
    a = api()
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
    assert a.migrate_identity(conn) == 2
    tables = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert tables == {"atp_lab_schema", "data_sources", "source_snapshots",
                      "players", "player_aliases", "tournaments", "matches",
                      "match_aliases", "fixture_versions", "result_versions"}
    before = conn.execute("SELECT type,name,sql FROM sqlite_master ORDER BY name").fetchall()
    assert a.migrate_identity(conn) == 2
    assert conn.execute("SELECT type,name,sql FROM sqlite_master ORDER BY name").fetchall() == before


def test_migration_rejects_forged_bootstrap(conn):
    a = api()
    conn.execute("CREATE TABLE unrelated (id INTEGER)")
    with pytest.raises(ValueError):
        a.migrate_identity(conn)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
    assert conn.execute("SELECT name FROM sqlite_master WHERE name='players'").fetchall() == []


def test_v2_schema_damage_not_silently_repaired(conn):
    a = api()
    a.migrate_identity(conn)
    conn.execute("DROP TABLE result_versions")
    with pytest.raises(ValueError):
        a.migrate_identity(conn)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 2


def test_synthetic_identity_round_trip(conn):
    a = seed(conn)
    conn.execute("BEGIN IMMEDIATE")
    assert a.append_fixture(conn, fixture(a)) is True
    assert a.append_result(conn, result(a)) is True
    conn.commit()
    assert conn.execute("SELECT canonical_a,canonical_b FROM matches").fetchone() == ("SYN-A", "SYN-B")
    assert conn.execute("SELECT player_id FROM player_aliases WHERE provider_player_id='p1'").fetchone() == ("SYN-A",)
    assert conn.execute("SELECT winner FROM result_versions").fetchone() == ("SYN-A",)
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_identical_replay_is_noop(conn):
    a = seed(conn)
    conn.execute("BEGIN IMMEDIATE")
    f = fixture(a)
    assert a.append_fixture(conn, f) is True
    assert a.append_fixture(conn, f) is False
    assert a.put_player(conn, a.Player("SYN-A")) is False
    conn.commit()
    assert conn.execute("SELECT count(*) FROM fixture_versions").fetchone()[0] == 1


def test_conflicting_replay_never_overwrites(conn):
    a = seed(conn)
    conn.execute("BEGIN IMMEDIATE")
    f = fixture(a)
    a.append_fixture(conn, f)
    with pytest.raises(ValueError):
        a.append_fixture(conn, replace(f, state="POSTPONED"))
    conn.commit()
    assert conn.execute("SELECT state FROM fixture_versions").fetchone()[0] == "SCHEDULED"


def test_alias_collision_requires_explicit_resolution(conn):
    a = seed(conn)
    conn.execute("BEGIN IMMEDIATE")
    with pytest.raises(ValueError):
        a.put_alias(conn, a.PlayerAlias("SYN-feed", "p1", "SYN-B"))
    conn.rollback()
    assert conn.execute("SELECT player_id FROM player_aliases").fetchone()[0] == "SYN-A"


def test_provider_match_alias_conflict_rejected(conn):
    a = seed(conn)
    conn.execute("BEGIN IMMEDIATE")
    a.put_match(conn, a.Match("SYN-m2", "SYN-t1", "SYN-A", "SYN-C"))
    with pytest.raises(ValueError):
        a.put_match_alias(conn, a.MatchAlias("SYN-feed", "m1", "SYN-m2"))
    conn.rollback()


@pytest.mark.parametrize("players", [("SYN-A", "SYN-A"), ("SYN-B", "SYN-A")])
def test_invalid_canonical_pair_rejected(conn, players):
    a = seed(conn)
    conn.execute("BEGIN IMMEDIATE")
    with pytest.raises((ValueError, sqlite3.IntegrityError)):
        a.put_match(conn, a.Match("SYN-bad", "SYN-t1", *players))
    conn.rollback()


def test_invalid_winner_rejected(conn):
    a = seed(conn)
    conn.execute("BEGIN IMMEDIATE")
    with pytest.raises((ValueError, sqlite3.IntegrityError)):
        a.append_result(conn, result(a, winner="SYN-C"))
    conn.rollback()


def test_cross_source_snapshot_mismatch_rejected(conn):
    a = seed(conn)
    conn.execute("BEGIN IMMEDIATE")
    with pytest.raises((ValueError, sqlite3.IntegrityError)):
        a.append_fixture(conn, fixture(a, snapshot_id="SYN-other-s"))
    conn.rollback()


def test_fixture_binding_cannot_change_canonical_pair(conn):
    a = seed(conn)
    conn.execute("BEGIN IMMEDIATE")
    with pytest.raises((ValueError, sqlite3.IntegrityError)):
        a.append_fixture(conn, fixture(a, player_b="SYN-C"))
    conn.rollback()


def test_revisions_append_and_preserve_previous_rows(conn):
    a = seed(conn)
    conn.execute("BEGIN IMMEDIATE")
    a.append_fixture(conn, fixture(a))
    a.append_fixture(conn, fixture(a, fixture_id="SYN-f2", revision=2,
                                   state="POSTPONED", scheduled_start=None))
    a.append_result(conn, result(a))
    a.append_result(conn, result(a, result_id="SYN-r2", revision=2, winner="SYN-B"))
    conn.commit()
    assert conn.execute("SELECT revision,state FROM fixture_versions ORDER BY revision").fetchall() == [(1,"SCHEDULED"), (2,"POSTPONED")]
    assert conn.execute("SELECT revision,winner FROM result_versions ORDER BY revision").fetchall() == [(1,"SYN-A"), (2,"SYN-B")]


def test_duplicate_revision_with_new_id_rejected(conn):
    a = seed(conn)
    conn.execute("BEGIN IMMEDIATE")
    a.append_fixture(conn, fixture(a))
    with pytest.raises((ValueError, sqlite3.IntegrityError)):
        a.append_fixture(conn, fixture(a, fixture_id="SYN-conflict"))
    conn.rollback()


@pytest.mark.parametrize("sql", [
    "UPDATE fixture_versions SET state='POSTPONED' WHERE fixture_id='SYN-f1'",
    "DELETE FROM fixture_versions WHERE fixture_id='SYN-f1'",
    "UPDATE result_versions SET winner='SYN-B' WHERE result_id='SYN-r1'",
    "DELETE FROM result_versions WHERE result_id='SYN-r1'",
    "INSERT OR REPLACE INTO fixture_versions SELECT * FROM fixture_versions",
])
def test_database_revision_guards(conn, sql):
    a = seed(conn)
    conn.execute("BEGIN IMMEDIATE")
    a.append_fixture(conn, fixture(a))
    a.append_result(conn, result(a))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(sql)
    conn.rollback()


def test_batch_rollback_preserves_original_identity(conn):
    a = seed(conn)
    conn.execute("BEGIN IMMEDIATE")
    a.put_player(conn, a.Player("SYN-D"))
    a.append_fixture(conn, fixture(a))
    conn.rollback()
    assert conn.execute("SELECT count(*) FROM players").fetchone()[0] == 3
    assert conn.execute("SELECT count(*) FROM fixture_versions").fetchone()[0] == 0


def test_permission_is_locked_and_real_source_rejected(conn):
    a = seed(conn)
    conn.execute("BEGIN IMMEDIATE")
    with pytest.raises((ValueError, sqlite3.IntegrityError)):
        a.put_source(conn, a.Source("SYN-live", "REAL", "LOCKED"))
    with pytest.raises((ValueError, sqlite3.IntegrityError)):
        a.put_source(conn, a.Source("SYN-unlocked", "SYNTHETIC", "ALLOWED"))
    conn.rollback()


def test_utc_normalization_and_unknown_availability(conn):
    a = seed(conn)
    conn.execute("BEGIN IMMEDIATE")
    a.append_fixture(conn, fixture(a, observed_at="2026-01-01T15:00:00+07:00",
                                   available_at=None))
    conn.commit()
    assert conn.execute("SELECT observed_at,available_at FROM fixture_versions").fetchone() == ("2026-01-01T08:00:00.000000Z", None)


@pytest.mark.parametrize("bad", ["2026-02-30T08:00:00Z", "2026-01-01T08:00:00"])
def test_invalid_or_naive_timestamp_rejected(conn, bad):
    a = seed(conn)
    conn.execute("BEGIN IMMEDIATE")
    with pytest.raises(ValueError):
        a.append_fixture(conn, fixture(a, observed_at=bad))
    conn.rollback()


def test_available_time_cannot_precede_local_observation(conn):
    a = seed(conn)
    conn.execute("BEGIN IMMEDIATE")
    with pytest.raises((ValueError, sqlite3.IntegrityError)):
        a.append_fixture(conn, fixture(a, available_at="2026-01-01T07:59:00Z"))
    conn.rollback()


def test_unknown_result_clocks_remain_null(conn):
    a = seed(conn)
    conn.execute("BEGIN IMMEDIATE")
    a.append_result(conn, result(a, published_at=None, actual_start=None,
                                 available_at=None))
    conn.commit()
    assert conn.execute("SELECT published_at,actual_start,available_at FROM result_versions").fetchone() == (None,None,None)


def test_insert_api_requires_explicit_transaction(conn):
    a = seed(conn)
    with pytest.raises(ValueError):
        a.put_player(conn, a.Player("SYN-D"))
    assert conn.execute("SELECT count(*) FROM players").fetchone()[0] == 3
