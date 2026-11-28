"""Read-only comparison of a TML event with a separately reviewed reference.

Neither caller-supplied normalized rows nor hash/lineage declarations prove
source authenticity, independence, or permission. No import or scoring.
"""
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import date
from hashlib import sha256
import json
import re

from .tml_preflight import HistoricalCandidate, SnapshotInspection

_ROUNDS = ("R128", "R64", "R32", "R16", "QF", "SF", "F")
# A alone is ambiguous; numeric TML levels must match the reviewed tier.
_TIERS = {"ATP_250": ("A", "250"), "ATP_500": ("A", "500"),
          "MASTERS_1000": ("M",), "GRAND_SLAM": ("G",)}
_MAX_ROWS = 256


@dataclass(frozen=True)
class DrawScope:
    tml_event_id: str
    reference_event_id: str
    reference_source_id: str
    event_week: str
    end_day: str
    tier: str
    surface: str
    expected_rounds: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class ReferenceRow:
    match_id: str
    winner_id: str
    loser_id: str
    round: str
    score: str
    status: str
    match_day: str | None
    row_sha256: str


@dataclass(frozen=True)
class ReferenceDraw:
    source_id: str
    event_id: str
    snapshot_sha256: str
    tier: str
    surface: str
    rows: tuple[ReferenceRow, ...]


@dataclass(frozen=True)
class MatchLink:
    canonical_id: str
    tml_match_num: str
    reference_match_id: str


@dataclass(frozen=True)
class PlayerLink:
    tml_player_id: str
    reference_player_id: str


@dataclass(frozen=True)
class RowDecision:
    canonical_id: str
    status: str
    tml_row_sha256: str | None
    reference_row_sha256: str | None


@dataclass(frozen=True)
class DrawAudit:
    status: str
    expected_rows: int
    agreed_rows: int
    reference_days_present: int
    full_result_agreement: bool
    decisions: tuple[RowDecision, ...]
    unlinked_tml: tuple[str, ...]
    unlinked_reference: tuple[str, ...]
    findings: tuple[str, ...]
    audit_sha256: str
    source_independence_verified: bool = field(default=False, init=False)
    actual_start_verified: bool = field(default=False, init=False)
    import_allowed: bool = field(default=False, init=False)
    eligible_for_training: bool = field(default=False, init=False)
    eligible_for_scoring: bool = field(default=False, init=False)


def _id(value):
    return type(value) is str and re.fullmatch(r"[A-Za-z0-9_.:-]{1,120}", value) is not None


def _hash(value):
    return type(value) is str and re.fullmatch(r"[a-f0-9]{64}", value) is not None


def _day(value):
    if type(value) is not str or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError("explicit calendar date required")
    return date.fromisoformat(value)


def _match_num(value):
    return type(value) is str and re.fullmatch(r"[1-9][0-9]{0,7}", value) is not None


def _unique(values):
    return len(set(values)) == len(values)


def _bounded(items, row_type, limit):
    if type(items) is not tuple or len(items) > limit or any(type(x) is not row_type for x in items):
        raise ValueError("invalid or oversized audit inventory")


def _plausible_completed_score(score):
    # Conservative conventional singles set notation; not a best-of or
    # historical rulebook certification. Nonstandard formats need review.
    sets = score.split()
    if not 2 <= len(sets) <= 5:
        return False
    winners = []
    for item in sets:
        parsed = re.fullmatch(r"([0-9]{1,2})-([0-9]{1,2})(?:\(([0-9]{1,2})\))?", item)
        if parsed is None:
            return False
        a, b = map(int, parsed.groups()[:2])
        hi, lo = max(a, b), min(a, b)
        if not ((hi == 6 and lo <= 4) or (hi == 7 and lo in (5, 6))
                or (hi >= 8 and hi - lo == 2)):
            return False
        if parsed.group(3) is not None and (hi, lo) != (7, 6):
            return False
        winners.append(a > b)
    wins = sum(winners)
    return wins in (2, 3) and len(winners) - wins < wins and winners[-1]


def audit_draw(tml: SnapshotInspection, scope: DrawScope, reference: ReferenceDraw,
               match_links: tuple[MatchLink, ...], player_links: tuple[PlayerLink, ...], *,
               lineage: str = "UNKNOWN", lineage_evidence_sha256: str | None = None) -> DrawAudit:
    """Compare exact mapped rows; all outputs require human evidence review.

    Expected rounds come from a separately reviewed draw inventory, not either
    input feed. Lineage is a caller declaration, not a verified permission.
    The reference score must already be normalized to winner-first notation.
    """
    if type(tml) is not SnapshotInspection or type(scope) is not DrawScope or type(reference) is not ReferenceDraw:
        raise ValueError("typed inspection, scope and reference required")
    if (not all(_id(x) for x in (scope.tml_event_id, scope.reference_event_id, scope.reference_source_id))
            or scope.reference_source_id.casefold() in ("tml", "tennismylife")
            or tml.event_id != scope.tml_event_id or reference.event_id != scope.reference_event_id
            or reference.source_id != scope.reference_source_id or not _hash(tml.sha256)
            or not _hash(reference.snapshot_sha256) or tml.sha256 == reference.snapshot_sha256
            or scope.tier not in _TIERS or reference.tier != scope.tier
            or scope.surface not in ("HARD", "CLAY", "GRASS") or reference.surface != scope.surface):
        raise ValueError("incompatible event/source/tier/surface or snapshot hashes")
    start, end = _day(scope.event_week), _day(scope.end_day)
    if start > end or (end - start).days > 28 or start.year != tml.year:
        raise ValueError("invalid event date window")
    if (lineage not in ("UNKNOWN", "SHARED", "DISTINCT_REVIEWED")
            or (lineage_evidence_sha256 is not None and not _hash(lineage_evidence_sha256))
            or (lineage != "UNKNOWN" and not _hash(lineage_evidence_sha256))):
        raise ValueError("invalid lineage declaration/evidence")
    if type(scope.expected_rounds) is not tuple or not 0 < len(scope.expected_rounds) <= len(_ROUNDS):
        raise ValueError("expected draw inventory required")
    expected = {}
    for entry in scope.expected_rounds:
        if (type(entry) is not tuple or len(entry) != 2 or entry[0] not in _ROUNDS
                or entry[0] in expected or type(entry[1]) is not int or entry[1] <= 0):
            raise ValueError("invalid expected round inventory")
        expected[entry[0]] = entry[1]
    n = sum(expected.values())
    if n > _MAX_ROWS:
        raise ValueError("expected draw exceeds bound")
    _bounded(tml.candidates, HistoricalCandidate, _MAX_ROWS)
    _bounded(reference.rows, ReferenceRow, _MAX_ROWS)
    _bounded(match_links, MatchLink, _MAX_ROWS)
    _bounded(player_links, PlayerLink, 2 * _MAX_ROWS)
    if (type(tml.selected_rows) is not int or not 0 <= tml.selected_rows <= _MAX_ROWS
            or len(tml.candidates) > tml.selected_rows):
        raise ValueError("invalid TML inspection inventory")
    for row in tml.candidates:
        if (not _match_num(row.match_num) or not _hash(row.row_sha256)
                or not _id(row.winner_id) or not _id(row.loser_id) or row.winner_id == row.loser_id):
            raise ValueError("invalid TML candidate identity")
    for row in reference.rows:
        if (not all(_id(x) for x in (row.match_id, row.winner_id, row.loser_id))
                or row.winner_id == row.loser_id or not _hash(row.row_sha256)
                or row.round not in _ROUNDS or type(row.score) is not str or len(row.score) > 120
                or row.status not in ("COMPLETED", "RETIRED", "WALKOVER", "VOID", "UNKNOWN")):
            raise ValueError("invalid reference row")
        if row.match_day is not None:
            _day(row.match_day)
    for link in match_links:
        if not _id(link.canonical_id) or not _match_num(link.tml_match_num) or not _id(link.reference_match_id):
            raise ValueError("invalid match link")
    for link in player_links:
        if not _id(link.tml_player_id) or not _id(link.reference_player_id):
            raise ValueError("invalid player link")
    for records, key in ((tml.candidates, "match_num"), (reference.rows, "match_id"),
                         (match_links, "canonical_id"), (match_links, "tml_match_num"),
                         (match_links, "reference_match_id"), (player_links, "tml_player_id"),
                         (player_links, "reference_player_id")):
        if not _unique([getattr(x, key) for x in records]):
            raise ValueError("ambiguous duplicate ID or crosswalk")
    t = {row.match_num: row for row in tml.candidates}
    r = {row.match_id: row for row in reference.rows}
    players = {link.tml_player_id: link.reference_player_id for link in player_links}
    unlinked_t = tuple(sorted(t.keys() - {x.tml_match_num for x in match_links}))
    unlinked_r = tuple(sorted(r.keys() - {x.reference_match_id for x in match_links}))
    findings = set()
    if tml.quarantine or tml.quarantined_match_numbers:
        findings.add("TML_QUARANTINE")
    if (tml.selected_rows != n or Counter(x.round for x in t.values()) != expected
            or Counter(x.round for x in r.values()) != expected or len(match_links) != n):
        findings.add("DRAW_COVERAGE_MISMATCH")
    if unlinked_t or unlinked_r:
        findings.add("UNLINKED_ROWS")
    for rows in (t.values(), r.values()):
        appearances = Counter((row.round, player) for row in rows for player in (row.winner_id, row.loser_id))
        if any(count > 1 for count in appearances.values()):
            findings.add("ROUND_PLAYER_REUSE")
    days_present = sum(row.match_day is not None for row in r.values())
    if days_present != len(r):
        findings.add("REFERENCE_DAY_MISSING")
    decisions = []
    for link in sorted(match_links, key=lambda x: x.canonical_id):
        a, b = t.get(link.tml_match_num), r.get(link.reference_match_id)
        if a is None:
            reason = "TML_QUARANTINED" if link.tml_match_num in tml.quarantined_match_numbers else "TML_NOT_OBSERVED"
        elif b is None:
            reason = "REFERENCE_NOT_OBSERVED"
        elif a.tournament_week != scope.event_week or a.surface != scope.surface or a.provider_level not in _TIERS[scope.tier]:
            reason = "EVENT_METADATA_CONFLICT"
        elif a.winner_id not in players or a.loser_id not in players:
            reason = "MISSING_PLAYER_ALIAS"
        elif {players[a.winner_id], players[a.loser_id]} != {b.winner_id, b.loser_id}:
            reason = "PLAYER_CONFLICT"
        elif players[a.winner_id] != b.winner_id:
            reason = "OUTCOME_CONFLICT"
        elif b.status != "COMPLETED":
            reason = "NON_COMPLETED_REFERENCE"
        elif a.round != b.round:
            reason = "ROUND_CONFLICT"
        elif " ".join(a.score.split()) != " ".join(b.score.split()):
            reason = "SCORE_CONFLICT"
        elif not _plausible_completed_score(a.score):
            reason = "SCORE_REVIEW_REQUIRED"
        elif b.match_day is not None and not start <= _day(b.match_day) <= end:
            reason = "MATCH_DAY_OUTSIDE_EVENT"
        else:
            reason = "AGREES"
        decisions.append(RowDecision(link.canonical_id, reason, a.row_sha256 if a else None, b.row_sha256 if b else None))
    agreed = sum(d.status == "AGREES" for d in decisions)
    complete = agreed == n and not (findings - {"REFERENCE_DAY_MISSING"})
    if not complete:
        status = "CONFLICT_REVIEW_REQUIRED"
    elif lineage == "SHARED":
        status = "SHARED_LINEAGE_REVIEW_REQUIRED"
    elif lineage == "UNKNOWN":
        status = "LINEAGE_REVIEW_REQUIRED"
    else:
        status = "AGREEMENT_REVIEW_REQUIRED"
    # Canonicalize order and bind the actual normalized inputs and review claims.
    digest_input = {"tml": asdict(tml), "scope": asdict(scope), "reference": asdict(reference),
                    "matches": [asdict(x) for x in sorted(match_links, key=lambda x: x.canonical_id)],
                    "players": [asdict(x) for x in sorted(player_links, key=lambda x: x.tml_player_id)],
                    "lineage": lineage, "lineage_evidence_sha256": lineage_evidence_sha256}
    digest_input["tml"]["candidates"] = sorted(digest_input["tml"]["candidates"], key=lambda x: x["match_num"])
    digest_input["reference"]["rows"] = sorted(digest_input["reference"]["rows"], key=lambda x: x["match_id"])
    digest_input["scope"]["expected_rounds"] = sorted(scope.expected_rounds)
    digest = sha256(json.dumps(digest_input, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    return DrawAudit(status, n, agreed, days_present, complete, tuple(decisions), unlinked_t, unlinked_r,
                     tuple(sorted(findings)), digest)
