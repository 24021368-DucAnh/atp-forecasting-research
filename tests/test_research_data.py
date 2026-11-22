import csv
from pathlib import Path
import pytest
from atp_gate.research_data import load_historical_matches

COLS=['ATP','Tournament','Date','Series','Surface','Round','Best of','Winner','Loser','WRank','LRank','Comment','B365W','B365L']

def write_csv(p: Path, rows):
    with p.open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=COLS)
        writer.writeheader()
        writer.writerows(rows)
    return p

def row(**update):
    out=dict(ATP='1',Tournament='Melbourne',Date='11/01/2026',Series='Grand Slam',Surface='Hard',
      Round='1st Round',**{'Best of':'5'},Winner='Bravo B.',Loser='Alpha A.',WRank='12',LRank='9',
      Comment='Completed',B365W='2.20',B365L='1.70')
    out.update(update)
    return out

def test_result_label_is_not_always_player_a_and_odds_follow_player(tmp_path):
    data,audit=load_historical_matches(write_csv(tmp_path/'source.csv',[row()]))
    assert len(data)==1 and audit['accepted']==1
    m=data[0]
    assert m.player_a=='Alpha A.' and m.player_b=='Bravo B.'
    assert m.y==0 and m.odds_a==1.7 and m.odds_b==2.2
    assert m.rank_a==9 and m.rank_b==12
    assert m.tier=='GRAND_SLAM'
    assert audit['t60_live_eligible']==0 and audit['time_precision']=='DAY_ONLY'


def test_duplicate_and_invalid_rows_accounted_for(tmp_path):
    lines=[row(),row(),row(Tournament='Queens',Series='ATP500',**{'Best of':'5'}),
           row(Tournament='Paris',Date='bad'),row(Tournament='Davis',Series='Davis Cup'),
           row(Tournament='Indian Wells',Series='Masters 1000',Comment='Retired'),
           row(Tournament='Rome',B365W='',B365L='')]
    data,stats=load_historical_matches(write_csv(tmp_path/'f.csv',lines))
    assert len(data)==2
    assert stats['duplicate']==1 and stats['bad_format']==1 and stats['bad_date']==1
    assert stats['unsupported_tier']==1 and stats['not_completed']==1
    assert stats['missing_or_invalid_odds']==1
    assert data[-1].odds_a is None and data[-1].odds_b is None


def test_missing_required_columns_fail_fast(tmp_path):
    p=tmp_path/'bad.csv'
    p.write_text('Winner,Loser\nA,B\n',encoding='utf-8')
    with pytest.raises(ValueError,match='missing columns'):
        load_historical_matches(p)


def test_second_file_and_alias_duplicate_is_deduplicated(tmp_path):
    a=write_csv(tmp_path/'a.csv',[row()])
    b=write_csv(tmp_path/'b.csv',[row(Winner=' Bravo B. ',Loser=' Alpha A. ')])
    data,stats=load_historical_matches([a,b])
    assert len(data)==1
    assert stats['duplicate']==1


def test_official_excel_historical_file_with_datetime_cells(tmp_path):
    from openpyxl import Workbook
    from datetime import datetime
    wb=Workbook()
    ws=wb.active
    ws.append(COLS)
    sample=row()
    sample['Date']=datetime(2026,1,11)
    ws.append([sample[k] for k in COLS])
    p=tmp_path/'official.xlsx'
    wb.save(p)
    matches,audit=load_historical_matches(p)
    assert len(matches)==1
    assert matches[0].day.isoformat()=='2026-01-11'
    assert matches[0].y==0
    assert audit['time_precision']=='DAY_ONLY'


def test_research_audit_records_cryptographic_source_fingerprint(tmp_path):
    import hashlib
    p=write_csv(tmp_path/'source.csv',[row()])
    _matches,audit=load_historical_matches(p)
    expected=hashlib.sha256(p.read_bytes()).hexdigest()
    assert audit['source_files']==[{'name':'source.csv','sha256':expected,'size_bytes':p.stat().st_size}]


def test_tennis_data_atp_field_is_tournament_number_not_tour_filter(tmp_path):
    """Regression: real 2026.csv uses ATP=5 for Australian Open and ATP=16 for Indian Wells."""
    samples = [
        row(ATP='5', Tournament='Australian Open', Date='19/01/2026', Series='Grand Slam', Winner='Alpha A.', Loser='Bravo B.'),
        row(ATP='16', Tournament='Indian Wells', Date='10/03/2026', Series='Masters 1000', **{'Best of': '3'}, Winner='Charlie C.', Loser='Delta D.'),
        row(ATP='24', Tournament='Madrid', Date='24/04/2026', Series='Masters 1000', **{'Best of': '3'}, Winner='Echo E.', Loser='Foxtrot F.'),
        row(ATP='8', Tournament='Rotterdam', Date='11/02/2026', Series='ATP500', **{'Best of': '3'}, Winner='Golf G.', Loser='Hotel H.'),
    ]
    matches, audit = load_historical_matches(write_csv(tmp_path/'atp-2026.csv', samples))
    assert audit['accepted'] == 4
    assert audit['unsupported_tier'] == 0
    assert {m.tier for m in matches} == {'GRAND_SLAM', 'MASTERS_1000', 'ATP_500'}


def test_invalid_tournament_index_does_not_masquerade_as_atp_match(tmp_path):
    samples = [row(ATP='not-an-index')]
    matches, audit = load_historical_matches(write_csv(tmp_path/'bad-index.csv', samples))
    assert matches == []
    assert audit['bad_format'] == 1
    assert audit['unsupported_tier'] == 0
