"""Trusted DDL for synthetic-only identity schema v2."""
from contextlib import closing
import sqlite3

from .migrations import _MARKER, _MARKER_SQL, _objects, _transaction, _version

VERSION = 2

TABLES = (
    """CREATE TABLE data_sources (
        source_id TEXT PRIMARY KEY NOT NULL CHECK (source_id GLOB 'SYN-?*'),
        mode TEXT NOT NULL CHECK (mode = 'SYNTHETIC'),
        permission_status TEXT NOT NULL CHECK (permission_status = 'LOCKED')
    )""",
    """CREATE TABLE source_snapshots (
        snapshot_id TEXT PRIMARY KEY NOT NULL CHECK (snapshot_id GLOB 'SYN-?*'),
        source_id TEXT NOT NULL REFERENCES data_sources(source_id),
        digest TEXT NOT NULL CHECK (length(digest)=64 AND digest NOT GLOB '*[^0-9a-f]*'),
        observed_at TEXT NOT NULL,
        UNIQUE (source_id, snapshot_id)
    )""",
    """CREATE TABLE players (
        player_id TEXT PRIMARY KEY NOT NULL CHECK (player_id GLOB 'SYN-?*')
    )""",
    """CREATE TABLE player_aliases (
        source_id TEXT NOT NULL REFERENCES data_sources(source_id),
        provider_player_id TEXT NOT NULL CHECK (length(trim(provider_player_id)) > 0),
        player_id TEXT NOT NULL REFERENCES players(player_id),
        PRIMARY KEY (source_id, provider_player_id)
    )""",
    """CREATE TABLE tournaments (
        tournament_id TEXT PRIMARY KEY NOT NULL CHECK (tournament_id GLOB 'SYN-?*'),
        event_key TEXT NOT NULL CHECK (event_key GLOB 'SYN-?*'),
        edition TEXT NOT NULL CHECK (length(trim(edition)) > 0),
        tier TEXT NOT NULL CHECK (tier IN ('ATP250','ATP500','MASTERS1000','GRAND_SLAM','FINALS','OTHER')),
        surface TEXT NOT NULL CHECK (surface IN ('HARD','CLAY','GRASS','UNKNOWN')),
        UNIQUE (event_key, edition)
    )""",
    """CREATE TABLE matches (
        match_id TEXT PRIMARY KEY NOT NULL CHECK (match_id GLOB 'SYN-?*'),
        tournament_id TEXT NOT NULL REFERENCES tournaments(tournament_id),
        canonical_a TEXT NOT NULL REFERENCES players(player_id),
        canonical_b TEXT NOT NULL REFERENCES players(player_id),
        CHECK (canonical_a < canonical_b),
        UNIQUE (match_id, canonical_a, canonical_b)
    )""",
    """CREATE TABLE match_aliases (
        source_id TEXT NOT NULL REFERENCES data_sources(source_id),
        provider_match_id TEXT NOT NULL CHECK (length(trim(provider_match_id)) > 0),
        match_id TEXT NOT NULL REFERENCES matches(match_id),
        PRIMARY KEY (source_id, provider_match_id)
    )""",
    """CREATE TABLE fixture_versions (
        fixture_id TEXT PRIMARY KEY NOT NULL CHECK (fixture_id GLOB 'SYN-?*'),
        match_id TEXT NOT NULL,
        revision INTEGER NOT NULL CHECK (typeof(revision)='integer' AND revision > 0),
        source_id TEXT NOT NULL,
        snapshot_id TEXT NOT NULL,
        player_a TEXT NOT NULL,
        player_b TEXT NOT NULL,
        observed_at TEXT NOT NULL,
        available_at TEXT,
        scheduled_start TEXT,
        state TEXT NOT NULL CHECK (state IN ('SCHEDULED','POSTPONED','CANCELLED','UNKNOWN')),
        CHECK (available_at IS NULL OR available_at >= observed_at),
        CHECK (state <> 'SCHEDULED' OR scheduled_start IS NOT NULL),
        UNIQUE (match_id, source_id, revision),
        FOREIGN KEY (source_id, snapshot_id) REFERENCES source_snapshots(source_id, snapshot_id),
        FOREIGN KEY (match_id, player_a, player_b) REFERENCES matches(match_id, canonical_a, canonical_b)
    )""",
    """CREATE TABLE result_versions (
        result_id TEXT PRIMARY KEY NOT NULL CHECK (result_id GLOB 'SYN-?*'),
        match_id TEXT NOT NULL REFERENCES matches(match_id),
        revision INTEGER NOT NULL CHECK (typeof(revision)='integer' AND revision > 0),
        source_id TEXT NOT NULL,
        snapshot_id TEXT NOT NULL,
        observed_at TEXT NOT NULL,
        available_at TEXT,
        published_at TEXT,
        actual_start TEXT,
        state TEXT NOT NULL CHECK (state IN ('COMPLETED','RETIRED','WALKOVER','VOID','UNKNOWN')),
        winner TEXT REFERENCES players(player_id),
        CHECK (available_at IS NULL OR available_at >= observed_at),
        CHECK (published_at IS NULL OR published_at <= observed_at),
        CHECK (actual_start IS NULL OR actual_start <= observed_at),
        CHECK (actual_start IS NULL OR published_at IS NULL OR actual_start <= published_at),
        CHECK (state <> 'COMPLETED' OR winner IS NOT NULL),
        CHECK (state NOT IN ('VOID','UNKNOWN') OR winner IS NULL),
        UNIQUE (match_id, source_id, revision),
        FOREIGN KEY (source_id, snapshot_id) REFERENCES source_snapshots(source_id, snapshot_id)
    )""",
)

IMMUTABLE_TABLES = (
    "data_sources", "source_snapshots", "players", "player_aliases",
    "tournaments", "matches", "match_aliases", "fixture_versions",
    "result_versions", "atp_lab_schema",
)

TRIGGERS = tuple(
    f"CREATE TRIGGER immutable_{table}_{event.lower()} BEFORE {event} ON {table} "
    f"BEGIN SELECT RAISE(ABORT, 'immutable {table}'); END"
    for table in IMMUTABLE_TABLES
    for event in ("UPDATE", "DELETE")
) + tuple(
    f"CREATE TRIGGER {table}_snapshot_clock BEFORE INSERT ON {table} "
    "WHEN NEW.observed_at < (SELECT observed_at FROM source_snapshots "
    "WHERE snapshot_id=NEW.snapshot_id AND source_id=NEW.source_id) "
    "BEGIN SELECT RAISE(ABORT, 'revision precedes snapshot'); END"
    for table in ("fixture_versions", "result_versions")
) + (
    "CREATE TRIGGER result_winner_membership BEFORE INSERT ON result_versions "
    "WHEN NEW.winner IS NOT NULL AND NOT EXISTS "
    "(SELECT 1 FROM matches WHERE match_id=NEW.match_id "
    "AND NEW.winner IN (canonical_a, canonical_b)) "
    "BEGIN SELECT RAISE(ABORT, 'winner not in match'); END",
)

DDL = TABLES + TRIGGERS


def _expected_objects() -> list:
    # Use SQLite itself to normalize the trusted DDL and generate autoindexes.
    with closing(sqlite3.connect(":memory:")) as reference:
        reference.execute(_MARKER_SQL)
        for statement in DDL:
            reference.execute(statement)
        return _objects(reference)


def require_writer(conn: sqlite3.Connection) -> None:
    for pragma in ("foreign_keys", "recursive_triggers"):
        if conn.execute(f"PRAGMA {pragma}").fetchone()[0] != 1:
            raise ValueError(f"writer requires {pragma}=ON")


def migrate_identity(conn: sqlite3.Connection) -> int:
    """Upgrade exact bootstrap v1, or verify the exact identity v2 schema."""
    require_writer(conn)
    with _transaction(conn):
        version = _version(conn)
        objects = _objects(conn)
        if version == 1:
            if objects != [("table", "atp_lab_schema", _MARKER_SQL)]:
                raise ValueError("unrecognized bootstrap schema")
        elif version == VERSION:
            if objects != _expected_objects():
                raise ValueError("unrecognized identity schema")
        else:
            raise ValueError("unsupported identity migration version")
        if conn.execute("SELECT id, marker FROM atp_lab_schema").fetchall() != [(1, _MARKER)]:
            raise ValueError("unrecognized bootstrap marker")
        if version == 1:
            for statement in DDL:
                conn.execute(statement)
            conn.execute(f"PRAGMA user_version = {VERSION}")
        if _objects(conn) != _expected_objects():
            raise ValueError("identity schema verification failed")
        if conn.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise ValueError("identity foreign key violation")
    return VERSION
