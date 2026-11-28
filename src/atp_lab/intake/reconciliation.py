"""Pure fictional cross-source reconciliation; never certifies real scoring."""
from dataclasses import dataclass

from .policy import _clock, _hex, _id


@dataclass(frozen=True)
class Alias:
    source_id: str
    provider_match_id: str
    canonical_match_id: str
    event_id: str
    player_a: str
    player_b: str
    upstream_id: str


@dataclass(frozen=True)
class MatchObservation:
    source_id: str
    provider_match_id: str
    revision: int
    evidence_id: str
    event_id: str
    player_a: str
    player_b: str
    state: str
    winner: str|None
    observed_at: str
    available_at: str|None
    actual_start: str|None
    published_at: str|None
    scope: str='ATP_MEN_SINGLES_MAIN_DRAW'


@dataclass(frozen=True)
class Reconciliation:
    status: str
    reason: str
    canonical_match_id: str|None=None
    evidence_ids: tuple[str,...]=()
    effective_ids: tuple[str,...]=()
    timing_complete: bool=False
    eligible_for_scoring: bool=False


def reconcile(observations, crosswalk):
    """One canonical match from retained append-only fictional history.

    Missing timing can only yield historical-only. Distinct upstream labels
    are synthetic claims, not proof of independent real providers.
    """
    def deny(reason):
        ids=tuple(sorted({o.evidence_id for o in observations if type(o) is MatchObservation and _hex(o.evidence_id)})) if type(observations) in (tuple,list) and len(observations)<=4096 else ()
        return Reconciliation('QUARANTINE',reason,evidence_ids=ids)
    if (type(observations) not in (tuple,list) or not 0<len(observations)<=4096
        or type(crosswalk) not in (tuple,list) or len(crosswalk)>4096):
        return deny('INVALID_INVENTORY')
    aliases={}
    for a in crosswalk:
        if (type(a) is not Alias or not all(_id(x) for x in (a.source_id,a.canonical_match_id,a.event_id,a.player_a,a.player_b,a.upstream_id))
            or not a.player_a<a.player_b or type(a.provider_match_id) is not str or not 0<len(a.provider_match_id)<=120):
            return deny('INVALID_ALIAS')
        key=(a.source_id,a.provider_match_id)
        if key in aliases and aliases[key]!=a: return deny('IDENTITY_CONFLICT')
        aliases[key]=a
    versions={}; evidence={}; canonical=set(); identities=set()
    for o in observations:
        if (type(o) is not MatchObservation or not _id(o.source_id) or type(o.provider_match_id) is not str
            or type(o.revision) is not int or o.revision<1 or not _hex(o.evidence_id)):
            return deny('INVALID_OBSERVATION')
        if o.scope!='ATP_MEN_SINGLES_MAIN_DRAW': return deny('INVALID_SCOPE')
        a=aliases.get((o.source_id,o.provider_match_id))
        if a is None: return deny('MISSING_ALIAS')
        if (o.event_id,o.player_a,o.player_b)!=(a.event_id,a.player_a,a.player_b): return deny('IDENTITY_CONFLICT')
        if o.state not in ('SCHEDULED','COMPLETED','VOID','WALKOVER','RETIRED','UNKNOWN') or (o.state=='COMPLETED' and o.winner not in (o.player_a,o.player_b)) or (o.state!='COMPLETED' and o.winner is not None):
            return deny('INVALID_OUTCOME')
        try:
            seen=_clock(o.observed_at); clocks=[_clock(x) if x is not None else None for x in (o.actual_start,o.published_at,o.available_at)]
            actual,pub,avail=clocks
            if any(x is not None and x>seen for x in clocks) or (actual is not None and pub is not None and actual>pub) or (pub is not None and avail is not None and pub>avail): return deny('INVALID_TIMING')
        except (ValueError,TypeError): return deny('INVALID_TIMING')
        canonical.add(a.canonical_match_id);identities.add((a.event_id,a.player_a,a.player_b))
        if o.evidence_id in evidence and evidence[o.evidence_id]!=o: return deny('REVISION_CONFLICT')
        evidence[o.evidence_id]=o
        stream=versions.setdefault((o.source_id,o.provider_match_id),{})
        if o.revision in stream and stream[o.revision]!=o: return deny('REVISION_CONFLICT')
        stream[o.revision]=o
    if len(canonical)!=1: return deny('CANONICAL_MATCH_CONFLICT')
    if len(identities)!=1: return deny('IDENTITY_CONFLICT')
    latest=[]; upstream=set(); sources=set()
    for key,stream in versions.items():
        if key[0] in sources: return deny('SOURCE_ALIAS_CONFLICT')
        sources.add(key[0])
        ordered=sorted(stream.values(),key=lambda x:x.revision)
        if any(o.revision!=i for i,o in enumerate(ordered,1)): return deny('REVISION_GAP')
        if any(b.observed_at<=a.observed_at for a,b in zip(ordered,ordered[1:])): return deny('REVISION_CONFLICT')
        latest.append(ordered[-1]);upstream.add(aliases[key].upstream_id)
    if len({(o.state,o.winner) for o in latest})!=1: return deny('OUTCOME_CONFLICT')
    for name in ('actual_start','published_at'):
        if len({getattr(o,name) for o in latest if getattr(o,name) is not None})>1: return deny('TIMING_CONFLICT')
    ids=tuple(sorted(evidence));effective=tuple(sorted(o.evidence_id for o in latest));mid=next(iter(canonical))
    if len(upstream)<2: return Reconciliation('UNCONFIRMED','INSUFFICIENT_INDEPENDENCE',mid,ids,effective)
    complete=all(o.state=='COMPLETED' and o.actual_start and o.published_at and o.available_at for o in latest)
    return Reconciliation('CORROBORATED' if complete else 'HISTORICAL_ONLY',
        'SYNTHETIC_CORROBORATION' if complete else 'MISSING_TIMING_OR_COMPLETED_RESULT',mid,ids,effective,complete)
