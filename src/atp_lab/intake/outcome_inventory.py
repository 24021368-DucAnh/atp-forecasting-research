"""Review-only inventory of normalized historical main-draw outcomes.

Inputs are caller claims bound to source/row digests, not authenticated raw
bytes or official identities. Keep completed-result audit semantics separate.
No transport, persistence, timestamp inference or eligibility decisions.
"""
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import date
from hashlib import sha256
import json
import re

_ROUNDS = ('R128', 'R64', 'R32', 'R16', 'QF', 'SF', 'F')
_LEVELS = {'ATP_250': ('A', '250'), 'ATP_500': ('A', '500'),
           'MASTERS_1000': ('M',), 'GRAND_SLAM': ('G',)}
_STATUSES = ('COMPLETED', 'RETIRED', 'WALKOVER', 'VOID', 'UNKNOWN')
_LIMIT = 256


@dataclass(frozen=True)
class Edition:
    source_id: str
    event_id: str
    provider_level: str


@dataclass(frozen=True)
class InventoryScope:
    left: Edition
    right: Edition
    tier: str
    surface: str
    event_week: str
    end_day: str
    best_of: int
    expected_rounds: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class OutcomeRow:
    match_id: str
    round: str
    player_a: str
    player_b: str
    winner_id: str | None
    score: str  # winner-first for decided outcomes, never inferred
    status: str
    row_sha256: str
    event_week: str
    provider_level: str
    surface: str
    best_of: int
    match_day: str | None


@dataclass(frozen=True)
class Inventory:
    source_id: str
    event_id: str
    snapshot_sha256: str
    rows: tuple[OutcomeRow, ...]


@dataclass(frozen=True)
class OutcomeLink:
    slot_id: str  # explicit review alias, not a verified canonical match ID
    left_id: str
    right_id: str


@dataclass(frozen=True)
class PlayerAlias:
    left_id: str
    right_id: str


@dataclass(frozen=True)
class InventoryAudit:
    status: str
    expected_rows: int
    left_rows: int
    right_rows: int
    both_round_inventories_complete: bool
    full_inventory_agreement: bool
    completed_agreements: int
    non_completed_agreements: int
    unresolved_slots: int
    unlinked_left: int
    unlinked_right: int
    reference_days_present: int
    decisions: tuple[tuple[str, int], ...]
    findings: tuple[str, ...]
    audit_sha256: str
    canonical_ids_verified: bool = field(default=False, init=False)
    source_independence_verified: bool = field(default=False, init=False)
    actual_start_verified: bool = field(default=False, init=False)
    publication_time_verified: bool = field(default=False, init=False)
    import_allowed: bool = field(default=False, init=False)
    eligible_for_training: bool = field(default=False, init=False)
    eligible_for_scoring: bool = field(default=False, init=False)


def _id(x):
    return type(x) is str and re.fullmatch(r'[A-Za-z0-9_.:-]{1,120}', x) is not None


def _digest(x):
    return type(x) is str and re.fullmatch(r'[a-f0-9]{64}', x) is not None


def _day(x):
    if type(x) is not str or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', x):
        raise ValueError('explicit calendar date required')
    return date.fromisoformat(x)


def _bounded(items, kind, limit=_LIMIT):
    if type(items) is not tuple or len(items) > limit or any(type(x) is not kind for x in items):
        raise ValueError('invalid bounded inventory')


def _unique(items, *fields):
    for name in fields:
        if len({getattr(x, name) for x in items}) != len(items):
            raise ValueError('duplicate row or ambiguous review link')


def _expected(scope):
    if type(scope) is not InventoryScope or type(scope.left) is not Edition or type(scope.right) is not Edition:
        raise ValueError('typed reviewed scope required')
    if (type(scope.tier) is not str or scope.tier not in _LEVELS or scope.surface not in ('HARD', 'CLAY', 'GRASS')
            or type(scope.best_of) is not int or scope.best_of not in (3, 5)):
        raise ValueError('invalid reviewed tier/surface/format')
    for e in (scope.left, scope.right):
        if not _id(e.source_id) or not _id(e.event_id) or e.provider_level not in _LEVELS[scope.tier]:
            raise ValueError('invalid reviewed source edition/level')
    if scope.left.source_id.casefold() == scope.right.source_id.casefold():
        raise ValueError('distinct source declarations required')
    start, end = _day(scope.event_week), _day(scope.end_day)
    if not 0 <= (end-start).days <= 28:
        raise ValueError('invalid event window')
    expected = {}
    if type(scope.expected_rounds) is not tuple or not 0 < len(scope.expected_rounds) <= len(_ROUNDS):
        raise ValueError('explicit reviewed round inventory required')
    for item in scope.expected_rounds:
        if (type(item) is not tuple or len(item) != 2 or item[0] not in _ROUNDS
                or item[0] in expected or type(item[1]) is not int or item[1] <= 0):
            raise ValueError('invalid expected round count')
        expected[item[0]] = item[1]
    if sum(expected.values()) > _LIMIT:
        raise ValueError('oversized expected inventory')
    return expected, start, end


def _rows(inventory, edition):
    if (type(inventory) is not Inventory or (inventory.source_id, inventory.event_id) != (edition.source_id, edition.event_id)
            or not _digest(inventory.snapshot_sha256)):
        raise ValueError('source edition or snapshot mismatch')
    _bounded(inventory.rows, OutcomeRow)
    for r in inventory.rows:
        if (not all(_id(x) for x in (r.match_id, r.player_a, r.player_b)) or r.player_a == r.player_b
                or (r.winner_id is not None and r.winner_id not in (r.player_a, r.player_b))
                or not _digest(r.row_sha256) or r.round not in _ROUNDS or r.status not in _STATUSES
                or type(r.score) is not str or len(r.score) > 120
                or not _id(r.provider_level) or not _id(r.surface) or type(r.best_of) is not int):
            raise ValueError('invalid normalized outcome row')
        _day(r.event_week)
        if r.match_day is not None:
            _day(r.match_day)
    _unique(inventory.rows, 'match_id', 'row_sha256')
    return {r.match_id:r for r in inventory.rows}


def _score_valid(row):
    score = ' '.join(row.score.split())
    if row.status == 'VOID':
        return row.winner_id is None and score == 'VOID'
    if row.status == 'UNKNOWN' or row.winner_id is None:
        return False
    if row.status == 'WALKOVER':
        return score == 'W/O'
    retired = row.status == 'RETIRED'
    tokens = score.split()
    if retired:
        if not tokens or tokens.pop() != 'RET':
            return False
    if not 1 <= len(tokens) <= row.best_of:
        return False
    wins = losses = games = 0
    needed = row.best_of // 2 + 1
    for i, token in enumerate(tokens):
        m = re.fullmatch(r'([0-7])-([0-7])(?:\(([0-9]{1,2})\))?', token)
        if not m or max(wins, losses) >= needed:
            return False
        a, b = map(int, m.groups()[:2])
        hi, lo = max(a,b), min(a,b)
        games += a+b
        complete = (hi == 6 and lo <= 4) or (hi == 7 and lo in (5,6))
        if m[3] is not None and (hi,lo) != (7,6):
            return False
        if not complete:
            if not retired or i != len(tokens)-1 or hi > 6:
                return False
        elif a > b:
            wins += 1
        else:
            losses += 1
    if retired:
        return games > 0 and max(wins,losses) < needed
    return wins == needed and losses < needed


def _decision(a, b, scope, aliases, start, end, expected):
    if a is None or b is None:
        return 'LINK_TARGET_NOT_OBSERVED'
    for row, edition in ((a,scope.left),(b,scope.right)):
        if (row.event_week,row.provider_level,row.surface,row.best_of) != (scope.event_week,edition.provider_level,scope.surface,scope.best_of):
            return 'METADATA_CONFLICT'
    if a.round != b.round:
        return 'ROUND_CONFLICT'
    if a.round not in expected:
        return 'UNEXPECTED_ROUND'
    if a.player_a not in aliases or a.player_b not in aliases:
        return 'MISSING_PLAYER_ALIAS'
    if {aliases[a.player_a],aliases[a.player_b]} != {b.player_a,b.player_b}:
        return 'PLAYER_CONFLICT'
    if (aliases[a.winner_id] if a.winner_id is not None else None) != b.winner_id:
        return 'WINNER_CONFLICT'
    if a.status != b.status:
        return 'STATUS_CONFLICT'
    if not _score_valid(a) or not _score_valid(b):
        return 'OUTCOME_REVIEW_REQUIRED'
    if ' '.join(a.score.split()) != ' '.join(b.score.split()):
        return 'SCORE_CONFLICT'
    if (any(x is not None and not start <= _day(x) <= end for x in (a.match_day,b.match_day))
            or (a.match_day is not None and b.match_day is not None and a.match_day != b.match_day)):
        return 'MATCH_DAY_CONFLICT'
    return a.status + '_AGREEMENT'


def audit_inventory(scope: InventoryScope, left: Inventory, right: Inventory,
                    links: tuple[OutcomeLink, ...], aliases: tuple[PlayerAlias, ...]) -> InventoryAudit:
    """Report observed round counts and explicit cross-publication outcome agreement.

    A full inventory agreement is not full completed-result agreement or an
    official bracket certification. Missing observations never imply deletion.
    Only modern conventional tiebreak-set notation is supported; other formats
    remain unresolved. Input digests are claims, not authenticated receipts.
    """
    expected,start,end = _expected(scope)
    l,r = _rows(left,scope.left),_rows(right,scope.right)
    if left.snapshot_sha256 == right.snapshot_sha256:
        raise ValueError('distinct snapshot declarations required')
    _bounded(links,OutcomeLink)
    _bounded(aliases,PlayerAlias,2*_LIMIT)
    for link in links:
        if not all(_id(x) for x in (link.slot_id,link.left_id,link.right_id)):
            raise ValueError('invalid match review link')
    for alias in aliases:
        if not _id(alias.left_id) or not _id(alias.right_id):
            raise ValueError('invalid player review link')
    _unique(links,'slot_id','left_id','right_id')
    _unique(aliases,'left_id','right_id')
    mapping = {x.left_id:x.right_id for x in aliases}
    findings = set()
    counts_match = all(Counter(x.round for x in rows.values()) == expected for rows in (l,r))
    if not counts_match:
        findings.add('ROUND_INVENTORY_MISMATCH')
    for rows in (l,r):
        appearances = Counter((x.round,p) for x in rows.values() for p in (x.player_a,x.player_b))
        if any(n>1 for n in appearances.values()):
            findings.add('ROUND_PLAYER_REUSE')
    ul = len(l.keys()-{x.left_id for x in links})
    ur = len(r.keys()-{x.right_id for x in links})
    if ul or ur:
        findings.add('UNLINKED_ROWS')
    days = sum(x.match_day is not None for x in r.values())
    if days != len(r):
        findings.add('REFERENCE_DAY_MISSING')
    if any(x.match_day is None for x in l.values()):
        findings.add('LEFT_DAY_MISSING')
    decisions = Counter()
    agreed_by_round = Counter()
    for link in links:
        a, b = l.get(link.left_id), r.get(link.right_id)
        decision = _decision(a,b,scope,mapping,start,end,expected)
        decisions[decision] += 1
        if decision.endswith('_AGREEMENT'):
            agreed_by_round[a.round] += 1
    completed = decisions['COMPLETED_AGREEMENT']
    non_completed = sum(decisions[s+'_AGREEMENT'] for s in ('RETIRED','WALKOVER','VOID'))
    n = sum(expected.values())
    complete = (completed+non_completed==n==len(links) and not (findings-{'REFERENCE_DAY_MISSING','LEFT_DAY_MISSING'}))
    content = {'scope':asdict(scope),'left':asdict(left),'right':asdict(right),
               'links':[asdict(x) for x in sorted(links,key=lambda x:x.slot_id)],
               'aliases':[asdict(x) for x in sorted(aliases,key=lambda x:x.left_id)]}
    content['scope']['expected_rounds'] = sorted(scope.expected_rounds)
    for side in ('left','right'):
        content[side]['rows'] = sorted(content[side]['rows'],key=lambda x:x['match_id'])
    digest = sha256(json.dumps(content,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    return InventoryAudit('OUTCOME_INVENTORY_REVIEW_REQUIRED' if complete else 'CONFLICT_REVIEW_REQUIRED',
                          n,len(l),len(r),counts_match,complete,completed,non_completed,
                          sum(max(0,count-agreed_by_round[rnd]) for rnd,count in expected.items()),ul,ur,days,
                          tuple(sorted((k,v) for k,v in decisions.items() if v)),tuple(sorted(findings)),digest)
