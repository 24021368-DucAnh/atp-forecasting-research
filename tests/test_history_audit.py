from pathlib import Path
from atp_gate.historical_audit import audit_tennis_data_csv


def test_historical_csv_is_never_accepted_as_t60_live_quotes(tmp_path: Path):
    csv_text='''Date,Series,Tournament,Winner,Loser,Round,Surface,Best of,Comment,B365W,B365L
20/01/2026,Grand Slam,Australian Open,A,B,4th Round,Hard,5,Completed,1.70,2.10
20/01/2026,Grand Slam,Australian Open,A,B,4th Round,Hard,5,Completed,1.70,2.10
21/01/2026,ATP250,Some Open,C,D,1st Round,Hard,3,Completed,1.80,2.10
22/01/2026,ATP500,Some 500,E,F,1st Round,Hard,3,Completed,,
23/01/2026,Masters 1000,Some Masters,G,H,Quarterfinals,Clay,3,Walkover,1.75,2.10
24/01/2026,Masters 1000,Some Masters,I,J,Final,Clay,3,Retired,1.75,2.10
'''
    source = tmp_path / 'atp.csv'
    source.write_text(csv_text,encoding='utf-8')
    result = audit_tennis_data_csv(source)
    assert result['total_rows']==6
    assert result['tier_rows']==5
    assert result['duplicate_candidates']==1
    assert result['missing_odds']==1
    assert result['walkover']==1
    assert result['retired']==1
    assert result['date_precision']=='DAY_ONLY'
    assert result['t60_live_eligible']==0
    assert result['mode']=='HISTORICAL_RESEARCH_ONLY'


def test_bad_datetime_and_incorrect_best_of_are_quarantined(tmp_path: Path):
    source=tmp_path/'atp.csv'
    source.write_text('''Date,Series,Tournament,Winner,Loser,Round,Surface,Best of,Comment,B365W,B365L
not-a-date,ATP500,Some 500,A,B,F,Hard,3,Completed,1.80,2.10
20/01/2026,Grand Slam,Australian Open,A,B,F,Hard,3,Completed,1.70,2.10
''',encoding='utf-8')
    result=audit_tennis_data_csv(source)
    assert result['invalid_date']==1
    assert result['invalid_format']==1
    assert result['t60_live_eligible']==0
