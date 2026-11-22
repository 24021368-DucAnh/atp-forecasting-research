from datetime import date,timedelta
import random
import pytest
from atp_gate.research_data import HistoricalMatch
from atp_gate.research_train import run_research_from_matches,FEATURES_FOR_MODEL
from atp_gate.feature_schema import FEATURE_NAMES


def synthetic(n_days=120, per_day=4):
    players=[f'Player-{i:02d}' for i in range(20)]
    r=[]
    rng=random.Random(20261123)
    for day in range(n_days):
        d=date(2025,1,1)+timedelta(days=day)
        for j in range(per_day):
            i=(7*day+3*j)%20
            k=(i+1+day%7)%20
            names=sorted([players[i],players[k]])
            y=int(rng.random()<0.52)
            tier='ATP_500' if day%2==0 else 'ATP_250'
            r.append(HistoricalMatch(d,'Demo',tier,'R32','Hard' if day%3 else 'Clay',
                                     names[0],names[1],y,10+int(names[0].split("-")[-1]),10+int(names[1].split("-")[-1]),1.90,1.95,
                                     f'row-{day}-{j}'))
    return r


def test_temporal_training_calibration_and_test_are_disjoint():
    report=run_research_from_matches(synthetic(),minimum_total=90,minimum_target=20,seed=13)
    cuts=report['splits']
    assert cuts['train_end'] < cuts['calibrate_start']
    assert cuts['calibrate_end'] < cuts['holdout_start']
    assert cuts['train_n']>20 and cuts['calibrate_n']>10 and cuts['holdout_n']>10
    assert 0 <= report['holdout_target']['xgb_log_loss']
    assert 0 <= report['holdout_target']['elo_log_loss']
    assert report['holdout_target']['n']>=20


def test_report_never_authorizes_live_stake_or_trusted_registry():
    report=run_research_from_matches(synthetic(),minimum_total=90,minimum_target=20,seed=13)
    assert report['mode']=='HISTORICAL_RESEARCH_ONLY'
    assert report['live_eligible'] is False
    assert report['allocation_enabled'] is False
    assert report['validation_report_trusted'] is False
    assert 'trusted_validation_reports' not in report
    assert report['stake']==0


def test_model_features_exclude_odds_result_and_postmatch_data():
    assert list(FEATURES_FOR_MODEL)==list(FEATURE_NAMES)
    assert all('odds' not in x and x not in ('y','winner','score','w_1stWon') for x in FEATURES_FOR_MODEL)


def test_missing_market_odds_leave_market_comparison_empty():
    matches=[m.__class__(**{**m.__dict__,'odds_a':None,'odds_b':None}) for m in synthetic()]
    report=run_research_from_matches(matches,minimum_total=90,minimum_target=20,seed=13)
    assert report['market_comparison']['sample_n']==0
    assert report['market_comparison']['market_log_loss'] is None


def test_insufficient_temporal_data_cannot_be_scored():
    with pytest.raises(ValueError,match='insufficient|Insufficient'):
        run_research_from_matches(synthetic(n_days=7),minimum_total=90,minimum_target=20)


def test_research_model_report_keeps_feature_hash_and_training_config():
    from atp_gate.feature_schema import FEATURE_SCHEMA_HASH
    report=run_research_from_matches(synthetic(),minimum_total=90,minimum_target=20,seed=99)
    assert report['feature_audit']['feature_schema_hash']==FEATURE_SCHEMA_HASH
    assert report['training_configuration']['random_state']==99
    assert report['training_configuration']['n_estimators']==160
    assert report['training_configuration']['calibration']=='disjoint_platt_logit'
