"""Fictional normalized evidence only; no real source rows."""
from dataclasses import replace

import pytest


def inputs():
    from atp_lab.intake.outcome_inventory import (
        Edition, InventoryScope, Inventory, OutcomeRow, OutcomeLink, PlayerAlias,
    )
    left = Edition('TML', '2024-SYN-L', '500')
    right = Edition('REFERENCE', '2024-SYN-R', 'A')
    scope = InventoryScope(left, right, 'ATP_500', 'HARD', '2024-02-12',
                           '2024-02-18', 3, (('SF', 1), ('F', 1)))
    def row(mid, rnd, a, b, score, status, digest, level):
        return OutcomeRow(mid, rnd, a, b, a, score, status, digest * 64,
                          '2024-02-12', level, 'HARD', 3, None)
    a = Inventory(left.source_id, left.event_id, 'a'*64, (
        row('1','SF','L-A','L-B','6-4 6-3','COMPLETED','c','500'),
        row('2','F','L-A','L-C','4-6 1-1 RET','RETIRED','d','500')))
    b = Inventory(right.source_id, right.event_id, 'b'*64, (
        row('7','SF','R-A','R-B','6-4 6-3','COMPLETED','e','A'),
        row('8','F','R-A','R-C','4-6 1-1 RET','RETIRED','f','A')))
    links = (OutcomeLink('slot-1','1','7'), OutcomeLink('slot-2','2','8'))
    aliases = (PlayerAlias('L-A','R-A'), PlayerAlias('L-B','R-B'), PlayerAlias('L-C','R-C'))
    return scope, a, b, links, aliases


def run(*args):
    from atp_lab.intake.outcome_inventory import audit_inventory
    return audit_inventory(*(args or inputs()))


def test_retirement_is_observed_and_agrees_but_never_completed():
    result = run()
    assert result.expected_rows == result.left_rows == result.right_rows == 2
    assert result.both_round_inventories_complete and result.full_inventory_agreement
    assert result.status == 'OUTCOME_INVENTORY_REVIEW_REQUIRED'
    assert result.completed_agreements == 1 and result.non_completed_agreements == 1
    assert dict(result.decisions) == {'COMPLETED_AGREEMENT':1, 'RETIRED_AGREEMENT':1}
    assert result.unresolved_slots == 0 and result.reference_days_present == 0
    assert 'REFERENCE_DAY_MISSING' in result.findings
    assert not result.import_allowed and not result.eligible_for_training and not result.eligible_for_scoring
    assert not result.canonical_ids_verified and not result.source_independence_verified
    assert not result.actual_start_verified and not result.publication_time_verified
    with pytest.raises((TypeError,ValueError)):
        replace(result, import_allowed=True)


@pytest.mark.parametrize('status,score,winner,decision',[
    ('WALKOVER','W/O',True,'WALKOVER_AGREEMENT'),
    ('VOID','VOID',False,'VOID_AGREEMENT'),
    ('UNKNOWN','',False,'OUTCOME_REVIEW_REQUIRED'),
    ('RETIRED','6-4 6-4 RET',True,'OUTCOME_REVIEW_REQUIRED'),
    ('RETIRED','6-4 4-6 6-4 RET',True,'OUTCOME_REVIEW_REQUIRED'),
    ('RETIRED','0-0 RET',True,'OUTCOME_REVIEW_REQUIRED'),
    ('RETIRED','6-4 8-7 RET',True,'OUTCOME_REVIEW_REQUIRED'),
    ('RETIRED','6-4 1-1 RET extra',True,'OUTCOME_REVIEW_REQUIRED'),
    ('COMPLETED','6-4 6-4 6-4',True,'OUTCOME_REVIEW_REQUIRED'),
    ('COMPLETED','6-4 6-4 4-6',True,'OUTCOME_REVIEW_REQUIRED'),
    ('COMPLETED','6-4 4-6',True,'OUTCOME_REVIEW_REQUIRED'),
    ('WALKOVER','6-4 W/O',True,'OUTCOME_REVIEW_REQUIRED'),
    ('VOID','VOID',True,'OUTCOME_REVIEW_REQUIRED'),
])
def test_status_requires_consistent_score_and_winner(status,score,winner,decision):
    s,a,b,links,aliases=inputs()
    def change(i):
        return replace(i,rows=(i.rows[0],replace(i.rows[1],status=status,score=score,
                                                winner_id=i.rows[1].player_a if winner else None)))
    result=run(s,change(a),change(b),links,aliases)
    assert dict(result.decisions)[decision]==1
    assert result.completed_agreements==1
    assert result.full_inventory_agreement == decision.endswith('_AGREEMENT')
    assert result.non_completed_agreements == int(decision.endswith('_AGREEMENT'))
    assert result.both_round_inventories_complete and not result.import_allowed


@pytest.mark.parametrize('change,reason',[
    ({'winner_id':'R-C'},'WINNER_CONFLICT'),
    ({'player_b':'R-D'},'PLAYER_CONFLICT'),
    ({'round':'SF'},'ROUND_CONFLICT'),
    ({'score':'4-6 2-1 RET'},'SCORE_CONFLICT'),
    ({'status':'WALKOVER','score':'W/O'},'STATUS_CONFLICT'),
    ({'provider_level':'500'},'METADATA_CONFLICT'),
    ({'best_of':5},'METADATA_CONFLICT'),
    ({'surface':'CLAY'},'METADATA_CONFLICT'),
    ({'event_week':'2024-02-19'},'METADATA_CONFLICT'),
    ({'match_day':'2024-02-19'},'MATCH_DAY_CONFLICT'),
])
def test_mismatch_never_becomes_agreement(change,reason):
    s,a,b,links,aliases=inputs()
    result=run(s,a,replace(b,rows=(b.rows[0],replace(b.rows[1],**change))),links,aliases)
    assert dict(result.decisions)[reason]==1
    assert not result.full_inventory_agreement and result.unresolved_slots==1


def test_absence_and_unlinked_rows_are_distinct():
    s,a,b,links,aliases=inputs()
    missing=run(s,a,replace(b,rows=b.rows[:1]),links,aliases)
    assert not missing.both_round_inventories_complete
    assert dict(missing.decisions)['LINK_TARGET_NOT_OBSERVED']==1
    unlinked=run(s,a,b,links[:1],aliases)
    assert unlinked.both_round_inventories_complete and not unlinked.full_inventory_agreement
    assert (unlinked.unlinked_left,unlinked.unlinked_right)==(1,1)
    assert unlinked.unresolved_slots==1


@pytest.mark.parametrize('bad',['same-source','wrong-event','same-hash','duplicate-slot','duplicate-left',
                               'duplicate-player','bad-digest','duplicate-row','duplicate-expected','bad-tier'])
def test_invalid_evidence_contract_rejected(bad):
    s,a,b,links,aliases=inputs()
    if bad=='same-source': s=replace(s,right=replace(s.right,source_id='tml')); b=replace(b,source_id='tml')
    if bad=='wrong-event': b=replace(b,event_id='other')
    if bad=='same-hash': b=replace(b,snapshot_sha256=a.snapshot_sha256)
    if bad=='duplicate-slot': links=(links[0],replace(links[1],slot_id=links[0].slot_id))
    if bad=='duplicate-left': links=(links[0],replace(links[1],left_id=links[0].left_id))
    if bad=='duplicate-player': aliases+=(replace(aliases[1],left_id='L-D'),)
    if bad=='bad-digest': b=replace(b,rows=(replace(b.rows[0],row_sha256='bad'),b.rows[1]))
    if bad=='duplicate-row': b=replace(b,rows=(b.rows[0],replace(b.rows[1],match_id='7')))
    if bad=='duplicate-expected': s=replace(s,expected_rounds=(('F',1),('F',1)))
    if bad=='bad-tier': s=replace(s,tier='ATP_250')
    with pytest.raises(ValueError): run(s,a,b,links,aliases)


def test_two_missing_aliases_cannot_corrobate_players():
    s,a,b,links,aliases=inputs()
    result=run(s,a,b,links,aliases[1:])
    assert dict(result.decisions)=={'MISSING_PLAYER_ALIAS':2}
    assert result.unresolved_slots==2 and not result.full_inventory_agreement


def test_digest_binds_inputs_but_not_collection_order():
    s,a,b,links,aliases=inputs()
    first=run(s,a,b,links,aliases)
    reordered=run(replace(s,expected_rounds=s.expected_rounds[::-1]),replace(a,rows=a.rows[::-1]),
                  replace(b,rows=b.rows[::-1]),links[::-1],aliases[::-1])
    assert first==reordered
    assert run(s,a,replace(b,snapshot_sha256='0'*64),links,aliases).audit_sha256!=first.audit_sha256


def test_same_round_player_reuse_is_visible_even_with_exact_links():
    s,a,b,links,aliases=inputs()
    s=replace(s,expected_rounds=(('SF',2),))
    a=replace(a,rows=(a.rows[0],replace(a.rows[1],round='SF')))
    b=replace(b,rows=(b.rows[0],replace(b.rows[1],round='SF')))
    result=run(s,a,b,links,aliases)
    assert 'ROUND_PLAYER_REUSE' in result.findings and not result.full_inventory_agreement


def test_dates_are_not_filled_and_disagreement_is_not_ignored():
    s,a,b,links,aliases=inputs()
    a=replace(a,rows=(replace(a.rows[0],match_day='2024-02-16'),a.rows[1]))
    b=replace(b,rows=(replace(b.rows[0],match_day='2024-02-17'),b.rows[1]))
    result=run(s,a,b,links,aliases)
    assert dict(result.decisions)['MATCH_DAY_CONFLICT']==1
    assert result.reference_days_present==1 and not result.actual_start_verified


def test_agreement_in_unexpected_round_does_not_cover_missing_slot():
    s,a,b,links,aliases=inputs()
    a=replace(a,rows=(a.rows[0],replace(a.rows[1],round='QF')))
    b=replace(b,rows=(b.rows[0],replace(b.rows[1],round='QF')))
    result=run(s,a,b,links,aliases)
    assert dict(result.decisions)['UNEXPECTED_ROUND']==1
    assert result.unresolved_slots==1 and result.non_completed_agreements==0
    assert not result.both_round_inventories_complete


def test_extra_agreement_in_one_round_cannot_fill_missing_other_round():
    s,a,b,links,aliases=inputs()
    s=replace(s,expected_rounds=(('SF',1),('QF',1)))
    a=replace(a,rows=(a.rows[0],replace(a.rows[1],round='SF',player_a='L-D',winner_id='L-D')))
    b=replace(b,rows=(b.rows[0],replace(b.rows[1],round='SF',player_a='R-D',winner_id='R-D')))
    aliases=aliases+(replace(aliases[0],left_id='L-D',right_id='R-D'),)
    result=run(s,a,b,links,aliases)
    assert result.unresolved_slots==1
    assert not result.full_inventory_agreement
    assert 'ROUND_INVENTORY_MISMATCH' in result.findings


def test_reference_day_missing_distinguishes_left_only_gap():
    s,a,b,links,aliases=inputs()
    b=replace(b,rows=tuple(replace(x,match_day='2024-02-18') for x in b.rows))
    result=run(s,a,b,links,aliases)
    assert result.reference_days_present==2
    assert 'LEFT_DAY_MISSING' in result.findings
    assert 'REFERENCE_DAY_MISSING' not in result.findings
    assert result.full_inventory_agreement and not result.actual_start_verified
