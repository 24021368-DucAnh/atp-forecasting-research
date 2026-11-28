import csv
import hashlib
import io
import json
from dataclasses import replace

import pytest
from atp_gate.tml_historical_audit import TML_COLUMNS
from atp_lab.intake.tml_preflight import inspect_snapshot
from atp_lab.intake.draw_audit import (DrawScope, ReferenceDraw, ReferenceRow, MatchLink, PlayerLink, audit_draw)

CLOCK='2026-11-28T07:00:00Z'

def csv_bytes(columns, rows):
    f=io.StringIO(newline='')
    w=csv.DictWriter(f, fieldnames=columns)
    w.writeheader()
    for row in rows:
        w.writerow({k:row.get(k,'') for k in columns})
    return f.getvalue().encode('utf-8')

def row(level='500',event='2024-407',score='6-4 6-3',number='1',round='F',winner='P1',loser='P2',winner_name='Fictional One',loser_name='Fictional Two'):
    return {'tourney_id':event,'tourney_name':'Fictional event','surface':'Hard','draw_size':'32','tourney_level':level,'tourney_date':'20240212','match_num':number,'winner_id':winner,'loser_id':loser,'winner_name':winner_name,'loser_name':loser_name,'score':score,'best_of':'3','round':round}

def inspection(level,score='6-4 6-3'):
    payload=csv_bytes(TML_COLUMNS,[row(level,score=score)])
    return inspect_snapshot(payload,expected_sha256=hashlib.sha256(payload).hexdigest(),year=2024,event_id='2024-407',inspected_at=CLOCK),payload

@pytest.mark.parametrize('level',['250','500'])
def test_preserves_numeric_provider_level_and_original_row_digest(level):
    result,payload=inspection(level)
    assert result.sha256==hashlib.sha256(payload).hexdigest()
    assert len(result.candidates)==1
    candidate=result.candidates[0]
    assert candidate.provider_level==level
    assert candidate.canonical_tier is None
    parsed=next(csv.DictReader(io.StringIO(payload.decode())))
    expected=hashlib.sha256(json.dumps([parsed[c] for c in TML_COLUMNS],ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    assert candidate.row_sha256==expected
    assert not result.eligible_for_training and candidate.actual_start is None

@pytest.mark.parametrize('level,tier,expected', [('500','ATP_500','AGREES'),('250','ATP_250','AGREES'),('500','ATP_250','EVENT_METADATA_CONFLICT'),('250','ATP_500','EVENT_METADATA_CONFLICT'),('A','ATP_500','AGREES'),('A','ATP_250','AGREES'),('500','MASTERS_1000','EVENT_METADATA_CONFLICT')])
def test_draw_tier_binding(level,tier,expected):
    base,_=inspection('A')
    # Independent raw-level candidate; tests draw comparator without hiding a preflight failure.
    t=replace(base,candidates=(replace(base.candidates[0],provider_level=level),))
    scope=DrawScope('2024-407','2024-0407','SACKMANN-ARCHIVE','2024-02-12','2024-02-18',tier,'HARD',(('F',1),))
    ref=ReferenceDraw(scope.reference_source_id,scope.reference_event_id,'f'*64,tier,'HARD',(ReferenceRow('9','S1','S2','F','6-4 6-3','COMPLETED',None,'e'*64),))
    report=audit_draw(t,scope,ref,(MatchLink('AUDIT-1','1','9'),),(PlayerLink('P1','S1'),PlayerLink('P2','S2')))
    assert report.decisions[0].status==expected
    assert not report.import_allowed and not report.eligible_for_scoring

@pytest.mark.parametrize('level',['501','125','MISSING'])
def test_unknown_provider_level_quarantined(level):
    result,_=inspection(level)
    assert not result.candidates and dict(result.quarantine)=={'UNSUPPORTED_SCOPE':1}

def test_retirement_remains_quarantined_with_numeric_level():
    result,_=inspection('500','6-4 1-1 RET')
    assert not result.candidates and dict(result.quarantine)=={'OUTCOME_REVIEW_REQUIRED':1}
