"""Label-free synthetic fixtures and conservative point-in-time history."""
from dataclasses import dataclass, replace
from datetime import date
import re

from atp_lab.database.identity import utc_timestamp

EMBARGO_DAYS = 28
_SYN_ID = re.compile(r"SYN-[A-Za-z0-9._:-]+")


class TemporalError(ValueError):
    """Invalid synthetic identity, time or eligibility contract."""


@dataclass(frozen=True)
class UpcomingFixture:
    fixture_id: str
    match_id: str
    source_id: str
    revision: int
    tournament_id: str
    event_start: date
    surface: str
    player_a: str
    player_b: str
    observed_at: str
    available_at: str | None
    scheduled_start: str | None
    state: str


@dataclass(frozen=True)
class HistoricalResult:
    result_id: str
    match_id: str
    source_id: str
    revision: int
    tournament_id: str
    event_start: date
    surface: str
    player_a: str
    player_b: str
    observed_at: str
    available_at: str | None
    published_at: str | None
    actual_start: str | None
    state: str
    winner: str | None


def _clock(value, *, nullable=False):
    if nullable and value is None:
        return None
    try:
        return utc_timestamp(value)
    except (ValueError, TypeError):
        raise TemporalError("invalid UTC clock") from None


def _day(clock: str) -> date:
    return date.fromisoformat(clock[:10])


def _validate_identity(row, record_id):
    ids = (record_id, row.match_id, row.source_id, row.tournament_id,
           row.player_a, row.player_b)
    if any(type(value) is not str or _SYN_ID.fullmatch(value) is None
           for value in ids):
        raise TemporalError("invalid synthetic identity")
    if (type(row.revision) is not int
            or not 1 <= row.revision <= 9223372036854775807
            or type(row.event_start) is not date
            or type(row.surface) is not str
            or row.surface not in ("HARD", "CLAY", "GRASS")
            or row.player_a >= row.player_b):
        raise TemporalError("invalid synthetic event or match metadata")


def normalize_fixture(fixture: UpcomingFixture, *, cutoff: str) -> UpcomingFixture:
    """Validate one already-selected target, not a fixture revision inventory."""
    if type(fixture) is not UpcomingFixture:
        raise TemporalError("label-free fixture required")
    _validate_identity(fixture, fixture.fixture_id)
    limit = _clock(cutoff)
    observed = _clock(fixture.observed_at)
    available = _clock(fixture.available_at, nullable=True)
    scheduled = _clock(fixture.scheduled_start, nullable=True)
    if (type(fixture.state) is not str or fixture.state != "SCHEDULED"
            or available is None or scheduled is None
            or not observed <= available <= limit < scheduled
            or _day(scheduled) < fixture.event_start):
        raise TemporalError("target fixture not eligible at cutoff")
    return replace(fixture, observed_at=observed, available_at=available,
                   scheduled_start=scheduled)


def _normalize_result(row: HistoricalResult) -> HistoricalResult:
    if type(row) is not HistoricalResult:
        raise TemporalError("historical result required")
    _validate_identity(row, row.result_id)
    if (type(row.state) is not str
            or row.state not in ("COMPLETED", "RETIRED", "WALKOVER", "VOID", "UNKNOWN")):
        raise TemporalError("invalid result state")
    if ((row.winner is not None and
         (type(row.winner) is not str or row.winner not in (row.player_a, row.player_b)))
            or (row.state == "COMPLETED" and row.winner is None)
            or (row.state in ("VOID", "UNKNOWN") and row.winner is not None)):
        raise TemporalError("invalid result winner")
    observed = _clock(row.observed_at)
    available = _clock(row.available_at, nullable=True)
    published = _clock(row.published_at, nullable=True)
    actual = _clock(row.actual_start, nullable=True)
    if ((available is not None and available < observed)
            or (published is not None and published > observed)
            or (actual is not None and actual > observed)
            or (actual is not None and published is not None and actual > published)
            or (actual is not None and _day(actual) < row.event_start)):
        raise TemporalError("invalid historical result clock order")
    return replace(row, observed_at=observed, available_at=available,
                   published_at=published, actual_start=actual)


def select_history(fixture: UpcomingFixture,
                   results: tuple[HistoricalResult, ...] | list[HistoricalResult],
                   *, cutoff: str) -> tuple[HistoricalResult, ...]:
    """Select eligible synthetic outcomes from the as-of revision inventory.

    Structurally invalid rows fail closed, even if observed after cutoff.
    Valid future revisions are ignored before identity conflict checks.
    The latest observed revision blocks stale fallback when unavailable
    or ineligible. No cross-source reconciliation or trusted time claim.
    """
    limit = _clock(cutoff)
    target = normalize_fixture(fixture, cutoff=limit)
    if type(results) not in (list, tuple):
        raise TemporalError("invalid historical result collection")
    maturity_day = min(target.event_start, _day(limit))
    seen_ids = set()
    seen_revisions = set()
    metadata = {}
    latest = {}
    for item in results:
        row = _normalize_result(item)
        if row.observed_at > limit:
            continue
        key = (row.source_id, row.match_id, row.revision)
        if row.result_id in seen_ids or key in seen_revisions:
            raise TemporalError("duplicate visible result identity")
        seen_ids.add(row.result_id)
        seen_revisions.add(key)
        meta = (row.source_id, row.tournament_id, row.event_start, row.surface,
                row.player_a, row.player_b)
        if metadata.setdefault(row.match_id, meta) != meta:
            raise TemporalError("conflicting visible match identity")
        previous = latest.get(row.match_id)
        if previous is None or row.revision > previous.revision:
            latest[row.match_id] = row

    selected = []
    for row in latest.values():
        if row.match_id == target.match_id or row.tournament_id == target.tournament_id:
            continue
        if (row.state != "COMPLETED" or row.available_at is None
                or row.available_at > limit or row.published_at is None
                or row.actual_start is None
                or (maturity_day - row.event_start).days < EMBARGO_DAYS):
            continue
        selected.append(row)
    return tuple(sorted(selected, key=lambda row: (
        row.event_start, row.tournament_id, row.match_id, row.result_id)))
