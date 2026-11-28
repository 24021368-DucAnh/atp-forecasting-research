from dataclasses import replace
import pytest

T0='2026-11-28T10:00:00Z'; T1='2026-11-28T11:00:00Z'; T2='2026-11-28T12:00:00Z'


def fixture():
    from atp_lab.intake.reconciliation import MatchObservation, Alias
    a = Alias('SYN-a','match-a','SYN-match','SYN-event','SYN-A','SYN-B','SYN-upstream-a')
    b = replace(a, source_id='SYN-b', provider_match_id='match-b', upstream_id='SYN-upstream-b')
    x = MatchObservation('SYN-a','match-a',1,'a'*64,'SYN-event','SYN-A','SYN-B',
                         'COMPLETED','SYN-A',T2,T2,T0,T1)
    y = replace(x,source_id='SYN-b',provider_match_id='match-b',evidence_id='b'*64)
    return (x,y),(a,b)


def test_distinct_independent_sources_corroborate_without_scoring():
    from atp_lab.intake.reconciliation import reconcile
    rows, aliases=fixture(); d=reconcile(rows,aliases)
    assert (d.status,d.canonical_match_id,d.evidence_ids)==('CORROBORATED','SYN-match',('a'*64,'b'*64))
    assert d.timing_complete and not d.eligible_for_scoring
    assert reconcile(rows[::-1],aliases[::-1])==d


@pytest.mark.parametrize('case,reason',[('missing-alias','MISSING_ALIAS'),('bad-identity','IDENTITY_CONFLICT'),
    ('winner','OUTCOME_CONFLICT'),('shared-upstream','INSUFFICIENT_INDEPENDENCE'),
    ('revision','REVISION_CONFLICT'),('different-match','CANONICAL_MATCH_CONFLICT'),
    ('bad-timing','INVALID_TIMING'),('timing-conflict','TIMING_CONFLICT'),('invalid-scope','INVALID_SCOPE')])
def test_reconciliation_conflicts_never_vote_or_score(case,reason):
    from atp_lab.intake.reconciliation import reconcile
    (x,y),(a,b)=fixture(); rows=(x,y); aliases=(a,b)
    if case=='missing-alias': aliases=(a,)
    if case=='bad-identity': rows=(x,replace(y,player_b='SYN-C'))
    if case=='winner': rows=(x,replace(y,winner='SYN-B'))
    if case=='shared-upstream': aliases=(a,replace(b,upstream_id=a.upstream_id))
    if case=='revision': rows=(x,replace(x,evidence_id='c'*64,winner='SYN-B'),y)
    if case=='different-match': aliases=(a,replace(b,canonical_match_id='SYN-other'))
    if case=='bad-timing': rows=(x,replace(y,actual_start=T2,published_at=T1))
    if case=='timing-conflict': rows=(x,replace(y,actual_start='2026-11-28T10:30:00Z'))
    if case=='invalid-scope': rows=(x,replace(y,scope='DOUBLES'))
    d=reconcile(rows,aliases)
    assert d.reason==reason and not d.eligible_for_scoring
    assert d.status!='CORROBORATED'


def test_missing_clocks_stays_historical_only():
    from atp_lab.intake.reconciliation import reconcile
    (x,y),aliases=fixture()
    d=reconcile((replace(x,actual_start=None,published_at=None,available_at=None),y),aliases)
    assert d.status=='HISTORICAL_ONLY' and not d.timing_complete and not d.eligible_for_scoring


def test_corrections_reconcile_latest_but_preserve_prior_evidence():
    from atp_lab.intake.reconciliation import reconcile
    (x,y),aliases=fixture(); initial=reconcile((x,y),aliases)
    z=replace(x,revision=2,evidence_id='c'*64,observed_at='2026-11-28T13:00:00Z',available_at='2026-11-28T13:00:00Z')
    d=reconcile((x,y,z),aliases)
    assert d.status=='CORROBORATED' and d.evidence_ids==('a'*64,'b'*64,'c'*64)
    assert d.effective_ids==('b'*64,'c'*64)
    assert reconcile((x,y),aliases)==initial
    # A partial export adds no new observation: retained history remains effective.
    assert reconcile((x,y,z),aliases)==d


def test_same_source_cannot_claim_independence_with_two_aliases():
    from atp_lab.intake.reconciliation import reconcile
    (x,y),(a,b)=fixture()
    d=reconcile((x,replace(y,source_id=x.source_id)),(a,replace(b,source_id=a.source_id)))
    assert d.status=='QUARANTINE' and d.reason=='SOURCE_ALIAS_CONFLICT'


def test_quarantine_keeps_evidence_ids():
    from atp_lab.intake.reconciliation import reconcile
    (x,y),aliases=fixture()
    d=reconcile((x,replace(y,winner='SYN-B')),aliases)
    assert d.status=='QUARANTINE' and d.evidence_ids==('a'*64,'b'*64)


def test_missing_revision_not_certified():
    from atp_lab.intake.reconciliation import reconcile
    (x,y),aliases=fixture()
    d=reconcile((replace(x,revision=2),y),aliases)
    assert d.status=='QUARANTINE' and d.reason=='REVISION_GAP'
