"""Typed synthetic records and transactional, immutable identity inserts."""
from dataclasses import dataclass, fields
from datetime import datetime, timezone
import re
import sqlite3

from .schema_v2 import VERSION, migrate_identity, require_writer

_CLOCK = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})"
)
_ID = re.compile(r"SYN-[A-Za-z0-9._:-]+")


@dataclass(frozen=True)
class Source:
    source_id: str
    mode: str
    permission_status: str


@dataclass(frozen=True)
class Snapshot:
    snapshot_id: str
    source_id: str
    digest: str
    observed_at: str


@dataclass(frozen=True)
class Player:
    player_id: str


@dataclass(frozen=True)
class PlayerAlias:
    source_id: str
    provider_player_id: str
    player_id: str


@dataclass(frozen=True)
class Tournament:
    tournament_id: str
    event_key: str
    edition: str
    tier: str
    surface: str


@dataclass(frozen=True)
class Match:
    match_id: str
    tournament_id: str
    canonical_a: str
    canonical_b: str


@dataclass(frozen=True)
class MatchAlias:
    source_id: str
    provider_match_id: str
    match_id: str


@dataclass(frozen=True)
class Fixture:
    fixture_id: str
    match_id: str
    revision: int
    source_id: str
    snapshot_id: str
    player_a: str
    player_b: str
    observed_at: str
    available_at: str | None
    scheduled_start: str | None
    state: str


@dataclass(frozen=True)
class Result:
    result_id: str
    match_id: str
    revision: int
    source_id: str
    snapshot_id: str
    observed_at: str
    available_at: str | None
    published_at: str | None
    actual_start: str | None
    state: str
    winner: str | None


_RECORDS = {
    Source: ("data_sources", ("source_id",)),
    Snapshot: ("source_snapshots", ("snapshot_id",)),
    Player: ("players", ("player_id",)),
    PlayerAlias: ("player_aliases", ("source_id", "provider_player_id")),
    Tournament: ("tournaments", ("tournament_id",)),
    Match: ("matches", ("match_id",)),
    MatchAlias: ("match_aliases", ("source_id", "provider_match_id")),
    Fixture: ("fixture_versions", ("fixture_id",)),
    Result: ("result_versions", ("result_id",)),
}
_CLOCK_FIELDS = {"observed_at", "available_at", "scheduled_start", "published_at", "actual_start"}
_OPTIONAL = {"available_at", "scheduled_start", "published_at", "actual_start", "winner"}
_ID_FIELDS = {"source_id", "snapshot_id", "player_id", "tournament_id", "event_key",
              "match_id", "canonical_a", "canonical_b", "fixture_id", "result_id",
              "player_a", "player_b", "winner"}


def utc_timestamp(value: str) -> str:
    """Validate a known RFC3339 instant and normalize to fixed UTC microseconds."""
    if not isinstance(value, str) or _CLOCK.fullmatch(value) is None:
        raise ValueError("timestamp must be timezone-aware RFC3339")
    if value.endswith("-00:00"):
        raise ValueError("unknown UTC offset")
    if not value.endswith("Z") and (int(value[-5:-3]) > 23 or int(value[-2:]) > 59):
        raise ValueError("invalid UTC offset")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
            timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
    except (ValueError, OverflowError) as exc:
        raise ValueError("invalid timestamp") from exc


def _canonical(name: str, value):
    if value is None and name in _OPTIONAL:
        return None
    if name in _CLOCK_FIELDS:
        return utc_timestamp(value)
    if name == "revision":
        if type(value) is not int or not 1 <= value <= 9223372036854775807:
            raise ValueError("revision must be a positive SQLite integer")
        return value
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise ValueError(f"invalid {name}")
    if name in _ID_FIELDS and _ID.fullmatch(value) is None:
        raise ValueError(f"non-synthetic or invalid {name}")
    return value


def _insert(conn: sqlite3.Connection, record, record_type: type) -> bool:
    if type(record) is not record_type:
        raise ValueError("incorrect record type")
    require_writer(conn)
    if not conn.in_transaction:
        raise ValueError("explicit caller transaction required")
    if conn.execute("PRAGMA user_version").fetchone()[0] not in (VERSION, 3, 4):
        raise ValueError("identity schema v2, v3 or v4 required")
    table, keys = _RECORDS[record_type]
    values = {field.name: _canonical(field.name, getattr(record, field.name))
              for field in fields(record_type)}
    names = ", ".join(values)
    where = " AND ".join(f"{key} = ?" for key in keys)
    existing = conn.execute(
        f"SELECT {names} FROM {table} WHERE {where}",
        tuple(values[key] for key in keys),
    ).fetchone()
    payload = tuple(values.values())
    if existing is not None:
        if tuple(existing) != payload:
            raise ValueError("conflicting immutable record replay")
        return False
    placeholders = ", ".join("?" for _ in values)
    conn.execute(f"INSERT INTO {table} ({names}) VALUES ({placeholders})", payload)
    return True


def put_source(conn: sqlite3.Connection, record: Source) -> bool:
    return _insert(conn, record, Source)


def put_snapshot(conn: sqlite3.Connection, record: Snapshot) -> bool:
    return _insert(conn, record, Snapshot)


def put_player(conn: sqlite3.Connection, record: Player) -> bool:
    return _insert(conn, record, Player)


def put_alias(conn: sqlite3.Connection, record: PlayerAlias) -> bool:
    return _insert(conn, record, PlayerAlias)


def put_tournament(conn: sqlite3.Connection, record: Tournament) -> bool:
    return _insert(conn, record, Tournament)


def put_match(conn: sqlite3.Connection, record: Match) -> bool:
    return _insert(conn, record, Match)


def put_match_alias(conn: sqlite3.Connection, record: MatchAlias) -> bool:
    return _insert(conn, record, MatchAlias)


def append_fixture(conn: sqlite3.Connection, record: Fixture) -> bool:
    return _insert(conn, record, Fixture)


def append_result(conn: sqlite3.Connection, record: Result) -> bool:
    return _insert(conn, record, Result)
