"""Read-only TML historical snapshot inspection; never a real-data activation.

No downloads, file writes, canonical identity assertions, or model eligibility.
Only the caller's already-held, hash-qualified bytes are inspected.
"""
from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
import csv
import io
import json
import re

from atp_gate.tml_historical_audit import TML_COLUMNS
from atp_gate.tml_snapshot import MAX_BYTES, _check_csv

_ID = re.compile(r"[A-Za-z0-9_-]{1,80}")
_NUMBER = re.compile(r"[1-9][0-9]{0,7}")
_CLOCK = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
_SCORE = re.compile(r"\d{1,2}-\d{1,2}(?:\(\d{1,2}\))?(?: \d{1,2}-\d{1,2}(?:\(\d{1,2}\))?)+")
_ROUNDS = ("R128", "R64", "R32", "R16", "QF", "SF", "F")


@dataclass(frozen=True)
class HistoricalCandidate:
    match_num: str
    tournament_week: str
    winner_id: str
    loser_id: str
    provider_level: str
    surface: str
    round: str
    score: str
    row_sha256: str
    canonical_tier: None = field(default=None, init=False)
    actual_start: None = field(default=None, init=False)
    published_at: None = field(default=None, init=False)
    available_at: None = field(default=None, init=False)


@dataclass(frozen=True)
class SnapshotInspection:
    sha256: str
    year: int
    event_id: str
    inspected_at: str
    source_rows: int
    source_anomalies: tuple[tuple[str, int], ...]
    selected_rows: int
    candidates: tuple[HistoricalCandidate, ...]
    quarantine: tuple[tuple[str, int], ...]
    quarantined_match_numbers: tuple[str, ...]
    status: str
    observed_at: None = field(default=None, init=False)
    eligible_for_training: bool = field(default=False, init=False)
    eligible_for_scoring: bool = field(default=False, init=False)


@dataclass(frozen=True)
class SnapshotChange:
    match_num: str
    status: str
    previous_row_sha256: str | None
    current_row_sha256: str | None


def _clock(value: str) -> datetime:
    if type(value) is not str or not _CLOCK.fullmatch(value):
        raise ValueError("inspection requires canonical UTC seconds")
    return datetime.fromisoformat(value[:-1] + "+00:00")


def _reason(row: dict, inspected: datetime) -> str | None:
    if None in row or any(value is None for value in row.values()):
        return "MALFORMED_ROW"
    if not _NUMBER.fullmatch(row["match_num"]):
        return "MISSING_MATCH_ID" if not row["match_num"] else "INVALID_MATCH_ID"
    if (not _ID.fullmatch(row["winner_id"]) or not _ID.fullmatch(row["loser_id"])
            or row["winner_id"] == row["loser_id"]):
        return "INVALID_PLAYER_IDS"
    # TML publishes both legacy A and numeric 250/500 levels; keep the raw
    # provider code. The reviewed draw scope decides the official tier.
    if row["tourney_level"] not in ("A", "G", "M", "F", "250", "500") or row["round"] not in _ROUNDS:
        return "UNSUPPORTED_SCOPE"
    if row["surface"].upper() not in ("HARD", "CLAY", "GRASS"):
        return "UNKNOWN_SURFACE"
    if row["best_of"] not in ("3", "5") or not _SCORE.fullmatch(row["score"]):
        return "OUTCOME_REVIEW_REQUIRED"
    if datetime.strptime(row["tourney_date"], "%Y%m%d").date() > inspected.date():
        return "FUTURE_EVENT_DATE"
    return None


def inspect_snapshot(payload: bytes, *, expected_sha256: str, year: int,
                     event_id: str, inspected_at: str) -> SnapshotInspection:
    """Inspect one event in a pinned seasonal CSV using the P1.5 validator.

    inspected_at is the caller's inspection time, not a historical receipt.
    Candidate rows still need canonical identity/outcome/rights review.
    """
    inspected = _clock(inspected_at)
    if type(year) is not int or not 1968 <= year <= inspected.year:
        raise ValueError("invalid season")
    if type(event_id) is not str or not _ID.fullmatch(event_id):
        raise ValueError("one exact provider event ID required")
    if type(payload) is not bytes or not 0 < len(payload) <= MAX_BYTES:
        raise ValueError("invalid snapshot size or type")
    digest = sha256(payload).hexdigest()
    if type(expected_sha256) is not str or expected_sha256 != digest:
        raise ValueError("snapshot digest mismatch")
    total, _, source_anomalies = _check_csv(payload, year)
    selected = 0
    quarantine: dict[str, int] = {}
    quarantined: set[str] = set()
    seen: set[str] = set()
    candidates = []
    reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig"), newline=""), strict=True)
    for row in reader:
        if row.get("tourney_id") != event_id:
            continue
        selected += 1
        number = row.get("match_num")
        valid_number = type(number) is str and _NUMBER.fullmatch(number) is not None
        if valid_number:
            if number in seen:
                raise ValueError("duplicate selected match identifier")
            seen.add(number)
        reason = _reason(row, inspected)
        if reason:
            quarantine[reason] = quarantine.get(reason, 0) + 1
            if valid_number:
                quarantined.add(number)
            continue
        row_digest = sha256(json.dumps([row[k] for k in TML_COLUMNS],
                                       ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
        candidates.append(HistoricalCandidate(number,
            datetime.strptime(row["tourney_date"], "%Y%m%d").date().isoformat(),
            row["winner_id"], row["loser_id"], row["tourney_level"],
            row["surface"].upper(), row["round"], row["score"], row_digest))
    if len({row.tournament_week for row in candidates}) > 1:
        raise ValueError("one event cannot span multiple candidate tournament weeks")
    return SnapshotInspection(digest, year, event_id, inspected_at, total,
        tuple(sorted(source_anomalies.items())), selected,
        tuple(sorted(candidates, key=lambda x: int(x.match_num))),
        tuple(sorted(quarantine.items())), tuple(sorted(quarantined, key=int)),
        "HISTORICAL_REVIEW_REQUIRED" if selected else "EVENT_NOT_OBSERVED")


def compare_snapshots(previous: SnapshotInspection,
                      current: SnapshotInspection) -> tuple[SnapshotChange, ...]:
    """Compare provider-local rows only; omissions never imply deletion."""
    if (type(previous) is not SnapshotInspection or type(current) is not SnapshotInspection
            or (previous.year, previous.event_id) != (current.year, current.event_id)
            or _clock(current.inspected_at) < _clock(previous.inspected_at)
            or (current.inspected_at == previous.inspected_at and current.sha256 != previous.sha256)):
        raise ValueError("incompatible snapshot inspection scope or clock")
    before = {row.match_num: row for row in previous.candidates}
    after = {row.match_num: row for row in current.candidates}
    changes = []
    for number in sorted(before.keys() | after.keys() | set(current.quarantined_match_numbers)
                         | set(previous.quarantined_match_numbers), key=int):
        a, b = before.get(number), after.get(number)
        if number in current.quarantined_match_numbers:
            status = "QUARANTINED"
        elif b is None:
            status = "NOT_OBSERVED"
        elif a is None:
            status = "REVIEW_RESOLVED" if number in previous.quarantined_match_numbers else "NEW"
        elif (a.tournament_week != b.tournament_week
              or {a.winner_id, a.loser_id} != {b.winner_id, b.loser_id}):
            status = "IDENTITY_CONFLICT"
        else:
            status = "UNCHANGED" if a.row_sha256 == b.row_sha256 else "CHANGED"
        changes.append(SnapshotChange(number, status,
            a.row_sha256 if a else None, b.row_sha256 if b else None))
    return tuple(changes)
