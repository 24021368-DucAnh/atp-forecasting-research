"""Chronological ATP research model. NOT a live/validated betting strategy.

XGBoost plus disjoint Platt calibration. Historical odds are used only as a
post-hoc comparator on identical holdout rows, never as a prediction feature.
"""
from __future__ import annotations

from pathlib import Path

from .feature_schema import FEATURE_NAMES, FEATURE_SCHEMA_HASH
from .research_data import HistoricalMatch, load_historical_matches

FEATURES_FOR_MODEL = FEATURE_NAMES
TARGET_TIERS = {'GRAND_SLAM', 'MASTERS_1000', 'ATP_500'}


def _score(y, p):
    from sklearn.metrics import brier_score_loss, log_loss
    return {'log_loss': round(float(log_loss(y, p, labels=[0, 1])), 6),
            'brier': round(float(brier_score_loss(y, p)), 6)}


def run_research_from_matches(matches: list[HistoricalMatch], *, minimum_total: int = 200,
                               minimum_target: int = 30, seed: int = 20261123) -> dict:
    """Fit/evaluate a research XGB. Returns no trusted report or live allocation."""
    try:
        import numpy as np
        import pandas as pd
        from sklearn.linear_model import LogisticRegression
        from xgboost import XGBClassifier
    except ImportError as exc:
        raise RuntimeError('Research ML packages missing: python -m pip install -e ".[ml,test]"') from exc
    from .research_features import replay_by_date

    frame = replay_by_date(matches)
    frame = frame[(frame['min_nm'] >= 5) & frame['y'].isin([0, 1])].copy()
    unique_dates = sorted(frame['date'].unique().tolist())
    if len(frame) < minimum_total or len(unique_dates) < 15:
        raise ValueError(f'Insufficient history: {len(frame)} eligible rows, {len(unique_dates)} dates; '
                         'add preceding seasons with player history')
    ix_train = max(1, int(len(unique_dates)*0.60))
    ix_cal = max(ix_train+1, int(len(unique_dates)*0.80))
    if ix_cal >= len(unique_dates):
        raise ValueError('Insufficient chronological dates for three independent partitions')
    cal_start = unique_dates[ix_train]
    test_start = unique_dates[ix_cal]
    train = frame[frame.date < cal_start]
    calibrate = frame[(frame.date >= cal_start) & (frame.date < test_start)]
    holdout = frame[frame.date >= test_start]
    test_tiers = holdout[holdout.tier.isin(TARGET_TIERS)]
    if min(len(train),len(calibrate),len(holdout)) < 15 or len(test_tiers) < minimum_target:
        raise ValueError('Insufficient chronological train/calibration/holdout or requested target-tier coverage')
    if train.y.nunique()<2 or calibrate.y.nunique()<2 or test_tiers.y.nunique()<2:
        raise ValueError('Insufficient outcome variation across temporal partitions')

    def xdata(df):
        # Only upstream-compatible pre-match features, no side labels or prices.
        return df.loc[:, list(FEATURES_FOR_MODEL)].astype('float32')

    model = XGBClassifier(n_estimators=160, max_depth=3, learning_rate=0.04,
                           subsample=0.9,colsample_bytree=0.9,min_child_weight=5,
                           reg_lambda=2.0,objective='binary:logistic',
                           eval_metric='logloss',random_state=seed,n_jobs=1)
    model.fit(xdata(train),train.y.astype(int))
    raw_cal=np.clip(model.predict_proba(xdata(calibrate))[:,1],1e-6,1-1e-6)
    # Platt calibration is fitted exclusively on intermediate chronological dates.
    logits_cal=np.log(raw_cal/(1-raw_cal)).reshape(-1,1)
    calibrator=LogisticRegression(random_state=seed,solver='lbfgs',max_iter=1000)
    calibrator.fit(logits_cal,calibrate.y.astype(int).to_numpy())

    def predict(df):
        raw=np.clip(model.predict_proba(xdata(df))[:,1],1e-6,1-1e-6)
        logits=np.log(raw/(1-raw)).reshape(-1,1)
        calibrated=calibrator.predict_proba(logits)[:,1]
        return raw,calibrated

    raw_target,p_target=predict(test_tiers)
    truth=test_tiers.y.astype(int).to_numpy()
    raw_metrics=_score(truth,raw_target)
    calibrated_metrics=_score(truth,p_target)
    elo_metrics=_score(truth,np.clip(test_tiers.p_elo.to_numpy(dtype=float),1e-6,1-1e-6))
    matched=test_tiers[test_tiers.odds_a.notna() & test_tiers.odds_b.notna()]
    market={'sample_n':len(matched),'market_log_loss':None,'market_brier':None,
            'xgb_same_rows_log_loss':None,'xgb_same_rows_brier':None,
            'elo_same_rows_log_loss':None}
    if len(matched):
        _,matched_p=predict(matched)
        m_truth=matched.y.astype(int).to_numpy()
        market_p=np.clip(matched.market_p_a.to_numpy(dtype=float),1e-6,1-1e-6)
        mp=_score(m_truth,market_p)
        xp=_score(m_truth,matched_p)
        ep=_score(m_truth,np.clip(matched.p_elo.to_numpy(dtype=float),1e-6,1-1e-6))
        market.update(market_log_loss=mp['log_loss'],market_brier=mp['brier'],
                      xgb_same_rows_log_loss=xp['log_loss'],xgb_same_rows_brier=xp['brier'],
                      elo_same_rows_log_loss=ep['log_loss'])
    return {
        'mode':'HISTORICAL_RESEARCH_ONLY',
        'model':'XGBOOST_PREMATCH_FEATURES_PLATT_RESEARCH',
        'source_matches':len(matches),
        'eligible_after_history':len(frame),
        'splits':{
            'train_n':len(train),'calibrate_n':len(calibrate),'holdout_n':len(holdout),
            'train_end':str(train.date.max()), 'calibrate_start':str(calibrate.date.min()),
            'calibrate_end':str(calibrate.date.max()), 'holdout_start':str(holdout.date.min()),
            'holdout_end':str(holdout.date.max())},
        'holdout_target':{'n':len(test_tiers),'tiers':sorted(TARGET_TIERS),
                          'xgb_log_loss':calibrated_metrics['log_loss'],
                          'xgb_brier':calibrated_metrics['brier'],
                          'xgb_uncalibrated_log_loss':raw_metrics['log_loss'],
                          'elo_log_loss':elo_metrics['log_loss'],
                          'elo_brier':elo_metrics['brier']},
        'market_comparison':market,
        'feature_audit':{
            'feature_schema_hash':FEATURE_SCHEMA_HASH,
            'feature_count':len(FEATURES_FOR_MODEL),
            'unavailable_from_historical_source':['spw_diff','rpw_diff','ace_diff','bps_diff'],
            'rank_diff_missing_ratio':round(float(frame['rank_diff'].isna().mean()),4),
            'serve_profile_absent':True,
            'identity': 'SOURCE_NAMES_NOT_VERIFIED_PLAYER_IDS',
            'match_time':'DAY_ONLY_NO_T60'},
        'live_eligible':False,'allocation_enabled':False,
        'validation_report_trusted':False,'stake':0,
        'warnings':[
            'Historical odds without quote timestamps cannot establish a tradable T-60 price.',
            'Outcome-ordered historical CSV is used solely as a label source; canonical pair order is independent of winner.',
            'Do not use this report as a trusted model registry or enable the V0.1 selection gate.',
            'One season or one holdout is insufficient to demonstrate persistent market edge.',
            'Model lacks serve/return stats absent from this historical source; training and live feature sets must match.',
        ],
        'random_seed':seed,
        'training_configuration':{
            'n_estimators':160, 'max_depth':3, 'learning_rate':0.04,
            'subsample':0.9, 'colsample_bytree':0.9,
            'min_child_weight':5, 'reg_lambda':2.0,
            'random_state':seed, 'calibration':'disjoint_platt_logit',
            'partition':'60_20_20_by_unique_dates'
        },
    }


def run_research(paths, *, minimum_total: int = 200, minimum_target: int = 30,
                 seed: int = 20261123) -> dict:
    matches,audit=load_historical_matches(paths)
    result=run_research_from_matches(matches,minimum_total=minimum_total,
                                    minimum_target=minimum_target,seed=seed)
    result['data_audit']=audit
    return result
