from datetime import date
import pandas as pd
import pytest
from atp_gate.research_data import HistoricalMatch
from atp_gate.research_features import replay_by_date
from atp_gate.feature_schema import FEATURE_NAMES


def mk(day, a, b, y, oa=1.8, ob=2.1, tier='ATP_500', surface='Hard', ra=10, rb=20):
    return HistoricalMatch(date.fromisoformat(day), 'Demo',tier,'R32',surface,a,b,y,ra,rb,oa,ob,day+'-'+a+'-'+b)


def test_day_batch_never_updates_same_day_features():
    matches=[mk('2026-01-01','A','B',1), mk('2026-01-01','A','C',0),
             mk('2026-01-02','A','D',1)]
    d=replay_by_date(matches)
    same=d[d['date']=='2026-01-01']
    assert list(same['p_elo']) == [pytest.approx(0.5),pytest.approx(0.5)]
    assert list(same['n_a']) == [0,0]
    assert d.iloc[2]['n_a']==2
    assert d.iloc[2]['date']=='2026-01-02'


def test_orientation_and_player_aligned_market_probability():
    d=replay_by_date([mk('2026-01-01','Alpha','Bravo',0,oa=1.7,ob=2.2,ra=9,rb=12)])
    r=d.iloc[0]
    assert r['y']==0 and r['rank_diff']==3.0
    assert r['odds_a']==1.7 and r['odds_b']==2.2
    assert r['market_p_a'] == pytest.approx((1/1.7)/((1/1.7)+(1/2.2)))
    assert not any('odds' in f or 'winner' in f or 'score' in f for f in FEATURE_NAMES)


def test_replay_includes_all_upstream_feature_names_without_fake_serve_data():
    d=replay_by_date([mk('2026-01-01','A','B',1)])
    assert set(FEATURE_NAMES).issubset(d.columns)
    for f in ('spw_diff','rpw_diff','ace_diff','bps_diff','sos_diff'):
        assert pd.isna(d.iloc[0][f])
    assert d.iloc[0]['min_nm']==0


def test_replay_requires_sorted_chronology_and_does_not_modify_input():
    matches=[mk('2026-01-02','A','C',1), mk('2026-01-01','A','B',1)]
    original=list(matches)
    d=replay_by_date(matches)
    assert list(d.date)==['2026-01-01','2026-01-02']
    assert matches==original
