"""Strict offline JSON normalization using an existing synthetic crosswalk."""
from dataclasses import dataclass
from hashlib import sha256
import json
import re
import sqlite3

from atp_lab.database.identity import Fixture, Result, Snapshot, utc_timestamp
from .adapter import (FetchedPayload, FIXTURES_ENDPOINT, RESULTS_ENDPOINT,
                      MAX_ATTEMPTS, MAX_BYTES)

MAX_ROWS = 1000
_SYN_ID = re.compile(r"SYN-[A-Za-z0-9._:-]+")
_COMMON = {"match_id", "player_1", "player_2", "revision", "state"}
_FIXTURE_FIELDS = _COMMON | {"scheduled_start"}
_RESULT_FIELDS = _COMMON | {"published_at", "actual_start", "winner"}


class ParseError(ValueError):
    """Sanitized synthetic data-quality failure."""


@dataclass(frozen=True)
class ParsedBatch:
    snapshot: Snapshot
    fixtures: tuple[Fixture, ...]
    results: tuple[Result, ...]


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ParseError("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _reject_constant(_value):
    raise ParseError("INVALID_JSON_CONSTANT")


def _stable_id(kind: str, *parts) -> str:
    encoded = json.dumps(parts, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    return f"SYN-{kind}-{sha256(encoded).hexdigest()}"


def _receipt_kind(receipt: FetchedPayload) -> str:
    if (type(receipt) is not FetchedPayload
            or type(receipt.source_id) is not str
            or _SYN_ID.fullmatch(receipt.source_id) is None
            or type(receipt.url) is not str
            or receipt.url not in (FIXTURES_ENDPOINT, RESULTS_ENDPOINT)
            or type(receipt.attempts) is not int
            or not 1 <= receipt.attempts <= MAX_ATTEMPTS
            or type(receipt.payload) is not bytes
            or not 1 <= len(receipt.payload) <= MAX_BYTES
            or type(receipt.digest) is not str
            or receipt.digest != sha256(receipt.payload).hexdigest()):
        raise ParseError("INVALID_RECEIPT")
    return "fixtures" if receipt.url == FIXTURES_ENDPOINT else "results"


def _clock(value, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    try:
        return utc_timestamp(value)
    except ValueError:
        raise ParseError("INVALID_CLOCK") from None


def _provider_id(value) -> str:
    if (type(value) is not str or not 1 <= len(value) <= 256
            or value != value.strip() or "\x00" in value):
        raise ParseError("INVALID_PROVIDER_ID")
    # JSON escapes can introduce lone surrogates even in valid UTF-8 bytes.
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeError:
        raise ParseError("INVALID_PROVIDER_ID") from None
    return value


def _player(conn, source_id: str, alias) -> str:
    row = conn.execute(
        "SELECT player_id FROM player_aliases WHERE source_id=? AND provider_player_id=?",
        (source_id, _provider_id(alias)),
    ).fetchone()
    if row is None:
        raise ParseError("UNKNOWN_PLAYER_ALIAS")
    return row[0]


def _match(conn, source_id: str, row: dict) -> tuple[str, str, str]:
    match = conn.execute(
        "SELECT m.match_id, m.canonical_a, m.canonical_b "
        "FROM match_aliases a JOIN matches m ON m.match_id=a.match_id "
        "WHERE a.source_id=? AND a.provider_match_id=?",
        (source_id, _provider_id(row["match_id"])),
    ).fetchone()
    if match is None:
        raise ParseError("UNKNOWN_MATCH_ALIAS")
    pair = sorted((_player(conn, source_id, row["player_1"]),
                   _player(conn, source_id, row["player_2"])))
    if pair[0] == pair[1] or tuple(pair) != tuple(match[1:]):
        raise ParseError("PARTICIPANT_MISMATCH")
    return tuple(match)


def _rows(payload: bytes, kind: str) -> list:
    try:
        document = json.loads(payload.decode("utf-8", errors="strict"),
                              object_pairs_hook=_unique_object,
                              parse_constant=_reject_constant)
    except ParseError:
        raise
    except (ValueError, RecursionError):
        raise ParseError("INVALID_JSON") from None
    if type(document) is not dict or set(document) != {kind}:
        raise ParseError("INVALID_BATCH_SCHEMA")
    rows = document[kind]
    if type(rows) is not list or len(rows) > MAX_ROWS:
        raise ParseError("INVALID_BATCH_SIZE")
    return rows


def parse_batch(conn: sqlite3.Connection, receipt: FetchedPayload, *,
                observed_at: str, available_at: str | None) -> ParsedBatch:
    """Normalize bounded fake input without database writes or network calls.

    Caller verifies v3 schema before entry; source scope is checked here.
    The receipt and supplied local clocks are not authenticated evidence.
    Operational SQLite errors propagate rather than masquerade as bad data.
    """
    kind = _receipt_kind(receipt)
    if conn.execute("PRAGMA user_version").fetchone()[0] != 3:
        raise ValueError("verified forecast schema v3 required")
    source = conn.execute(
        "SELECT mode, permission_status FROM data_sources WHERE source_id=?",
        (receipt.source_id,),
    ).fetchone()
    if source is None or tuple(source) != ("SYNTHETIC", "LOCKED"):
        raise ParseError("UNKNOWN_OR_INVALID_SOURCE")
    observed = _clock(observed_at)
    available = _clock(available_at, nullable=True)
    if available is not None and available < observed:
        raise ParseError("INVALID_LOCAL_CLOCK_ORDER")
    rows = _rows(receipt.payload, kind)
    snapshot = Snapshot(_stable_id("snapshot", receipt.source_id, receipt.url,
                                  receipt.digest, observed),
                        receipt.source_id, receipt.digest, observed)
    fixtures = []
    results = []
    seen = set()
    for row in rows:
        expected = _FIXTURE_FIELDS if kind == "fixtures" else _RESULT_FIELDS
        if type(row) is not dict or set(row) != expected:
            raise ParseError("INVALID_ROW_SCHEMA")
        revision = row["revision"]
        if type(revision) is not int or not 1 <= revision <= 9223372036854775807:
            raise ParseError("INVALID_REVISION")
        match_id, player_a, player_b = _match(conn, receipt.source_id, row)
        key = (match_id, revision)
        if key in seen:
            raise ParseError("DUPLICATE_CANONICAL_REVISION")
        seen.add(key)
        state = row["state"]
        if type(state) is not str:
            raise ParseError("INVALID_STATE")
        if kind == "fixtures":
            if state not in ("SCHEDULED", "POSTPONED", "CANCELLED", "UNKNOWN"):
                raise ParseError("INVALID_FIXTURE_STATE")
            scheduled = _clock(row["scheduled_start"], nullable=True)
            if state == "SCHEDULED" and scheduled is None:
                raise ParseError("MISSING_SCHEDULED_START")
            fixtures.append(Fixture(
                _stable_id("fixture", receipt.source_id, match_id, revision),
                match_id, revision, receipt.source_id, snapshot.snapshot_id,
                player_a, player_b, observed, available, scheduled, state))
        else:
            if state not in ("COMPLETED", "RETIRED", "WALKOVER", "VOID", "UNKNOWN"):
                raise ParseError("INVALID_RESULT_STATE")
            published = _clock(row["published_at"], nullable=True)
            actual = _clock(row["actual_start"], nullable=True)
            if ((published is not None and published > observed)
                    or (actual is not None and actual > observed)
                    or (actual is not None and published is not None and actual > published)):
                raise ParseError("INVALID_RESULT_CLOCK_ORDER")
            winner = None if row["winner"] is None else _player(
                conn, receipt.source_id, row["winner"])
            if ((winner is not None and winner not in (player_a, player_b))
                    or (state == "COMPLETED" and winner is None)
                    or (state in ("VOID", "UNKNOWN") and winner is not None)):
                raise ParseError("INVALID_WINNER")
            results.append(Result(
                _stable_id("result", receipt.source_id, match_id, revision),
                match_id, revision, receipt.source_id, snapshot.snapshot_id,
                observed, available, published, actual, state, winner))
    return ParsedBatch(snapshot, tuple(fixtures), tuple(results))
