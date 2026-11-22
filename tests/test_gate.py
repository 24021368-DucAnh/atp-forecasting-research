from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest
from pydantic import ValidationError
from atp_gate.contracts import Fixture, OddsQuote, FeatureSnapshot, ModelEvidence, RiskState, DecisionInput
from atp_gate.policy import evaluate as _evaluate, apply_profit_lock
from atp_gate.feature_schema import FeatureVector, FEATURE_SCHEMA_HASH

TEST_REGISTRY={"test-holdout-artifact": "a"*64}
def evaluate(data):
    return _evaluate(data, trusted_validation_reports=TEST_REGISTRY)

UTC = timezone.utc
T = datetime(2027, 1, 20, 9, tzinfo=UTC)

def valid(**changes):
    fixture = Fixture(match_id='fixture-001', event_id='event-1', player_a_id='ATP-A-100',
         player_b_id='ATP-B-200', competition='GRAND_SLAM', draw='MAIN', tour='ATP',
         gender='MEN', discipline='SINGLES', surface='HARD', best_of=5, round='R16',
         status='SCHEDULED', start_confirmed=True, scheduled_start=T+timedelta(hours=2),
         schedule_published_at=T-timedelta(hours=3), schedule_observed_at=T-timedelta(minutes=4),
         schedule_source='licensed_schedule')
    odds=OddsQuote(match_id='fixture-001', player_a_id='ATP-A-100', player_b_id='ATP-B-200', market='MATCH_WINNER', bookmaker='Examplebook', source_id='quote-id-1',
        decimal_odds_a=Decimal('1.90'), decimal_odds_b=Decimal('2.05'),
        observed_at=T-timedelta(minutes=4), published_at=T-timedelta(minutes=5),
        retrieved_at=T-timedelta(minutes=3), settlement_rule='RETIREMENT_ACTION')
    features=FeatureSnapshot(match_id='fixture-001', built_at=T-timedelta(minutes=10), data_asof=T-timedelta(minutes=11),
        feature_schema_hash=FEATURE_SCHEMA_HASH, critical_missing=[], imputed_fields=[],
        vector=FeatureVector(elo_diff=42.0,ov_diff=40.0,p_elo=0.55,
            form_p1=0.7,form_p2=0.5,h2h=0,rest_p1=3,rest_p2=4,
            rank_diff=20,min_nm=10,surface_clay=0,surface_grass=0,tour_wta=0,
            spw_diff=0.02,rpw_diff=0.01,ace_diff=0.01,bps_diff=0.02,sos_diff=20.0),
        matched_player_ids=True, duplicate_match_count=1, match_time_precise=True,
        source_license_ok=True, source_reconciliation_ok=True)
    evidence=ModelEvidence(match_id='fixture-001', model_id='model-v1', trained_until=T-timedelta(days=150),
        calibrated_from=T-timedelta(days=140), calibrated_until=T-timedelta(days=90),
        validated_until=T-timedelta(days=10), released_at=T-timedelta(days=1),
        predicted_at=T-timedelta(minutes=2), feature_schema_hash=FEATURE_SCHEMA_HASH,
        player_a_probability=0.60, player_a_prob_lower=0.56, player_a_prob_upper=0.64,
        validation_report_id='test-holdout-artifact', validation_report_sha256='a'*64, market_edge_verified=True,
        calibration_verified=True, validation_n=1500, selected_n=200)
    risk=RiskState(month='2027-01', free_cash=Decimal('1000'), open_exposure=Decimal('0'),
        phase='NORMAL', selections_today=0, month_loss_realized=Decimal('0'),
        week_loss_realized=Decimal('0'), annual_negative_month_loss=Decimal('0'),
        seen_match_ids=[])
    data=dict(as_of=T,fixture=fixture,odds=odds,features=features,model=evidence,risk=risk)
    data.update(changes)
    return DecisionInput(**data)


def test_valid_positive_lower_edge_selects_fractional_kelly_and_cap():
    ans=evaluate(valid())
    assert ans.decision=='SELECT'
    assert ans.side=='A'
    assert ans.stake==Decimal('10.00')
    assert ans.ev_lower == pytest.approx(0.064)


def test_no_trusted_holdout_evidence_abstains():
    data=valid(); m=data.model.model_copy(update={'market_edge_verified':False})
    ans=evaluate(data.model_copy(update={'model':m}))
    assert ans.decision=='ABSTAIN' and 'EDGE_NOT_VERIFIED' in ans.reasons


def test_missing_critical_data_abstains():
    data=valid(); f=data.features.model_copy(update={'critical_missing':['injury_status_unverified']})
    assert 'CRITICAL_FEATURE_MISSING' in evaluate(data.model_copy(update={'features':f})).reasons


def test_future_quote_abstains():
    data=valid(); quote=data.odds.model_copy(update={'observed_at': T+timedelta(minutes=1)})
    assert 'QUOTE_NOT_ASOF' in evaluate(data.model_copy(update={'odds':quote})).reasons


def test_stale_quote_abstains():
    data=valid(); quote=data.odds.model_copy(update={'observed_at':T-timedelta(hours=2), 'published_at':T-timedelta(hours=2,minutes=1)})
    assert 'QUOTE_STALE' in evaluate(data.model_copy(update={'odds':quote})).reasons


def test_unknown_retirement_rule_abstains():
    data=valid(); quote=data.odds.model_copy(update={'settlement_rule':'UNKNOWN'})
    assert 'SETTLEMENT_RULE_UNKNOWN' in evaluate(data.model_copy(update={'odds':quote})).reasons


def test_unknown_start_time_abstains():
    data=valid(); f=data.fixture.model_copy(update={'start_confirmed':False})
    assert 'START_UNCONFIRMED' in evaluate(data.model_copy(update={'fixture':f})).reasons


def test_less_than_60_min_to_start_abstains():
    data=valid(); f=data.fixture.model_copy(update={'scheduled_start':T+timedelta(minutes=50)})
    assert 'INSIDE_PREDICTION_CUTOFF' in evaluate(data.model_copy(update={'fixture':f})).reasons


def test_unsupported_or_started_event_abstains():
    data=valid(); f=data.fixture.model_copy(update={'status':'STARTED'})
    assert 'NOT_PREMATCH' in evaluate(data.model_copy(update={'fixture':f})).reasons


def test_duplicate_match_abstains():
    data=valid(); f=data.features.model_copy(update={'duplicate_match_count':2})
    assert 'AMBIGUOUS_MATCH' in evaluate(data.model_copy(update={'features':f})).reasons


def test_feature_schema_mismatch_abstains():
    data=valid(); f=data.features.model_copy(update={'feature_schema_hash':'wrong'})
    assert 'FEATURE_SCHEMA_MISMATCH' in evaluate(data.model_copy(update={'features':f})).reasons


def test_model_validation_cannot_be_future():
    data=valid(); m=data.model.model_copy(update={'validated_until':T+timedelta(days=1)})
    assert 'MODEL_NOT_ASOF' in evaluate(data.model_copy(update={'model':m})).reasons


def test_weekly_limit_blocks_even_if_kelly_positive():
    data=valid(); risk=data.risk.model_copy(update={'week_loss_realized':Decimal('30')})
    assert 'RISK_LIMIT_REACHED' in evaluate(data.model_copy(update={'risk':risk})).reasons


def test_two_open_orders_limit():
    data=valid(); risk=data.risk.model_copy(update={'open_exposure':Decimal('20'), 'free_cash':Decimal('980')})
    assert 'RISK_LIMIT_REACHED' in evaluate(data.model_copy(update={'risk':risk})).reasons


def test_loss_floor_caps_stake():
    data=valid(); risk=data.risk.model_copy(update={'free_cash':Decimal('953')})
    assert evaluate(data.model_copy(update={'risk':risk})).stake==Decimal('3.00')


def test_seen_match_id_blocks_repeat():
    data=valid(); risk=data.risk.model_copy(update={'seen_match_ids':['fixture-001']})
    assert 'DUPLICATE_SELECTION' in evaluate(data.model_copy(update={'risk':risk})).reasons


def test_profit_only_stake_respects_remaining_profit():
    data=valid(); risk=data.risk.model_copy(update={'free_cash':Decimal('10'), 'phase':'PROFIT_ONLY'})
    assert evaluate(data.model_copy(update={'risk':risk})).decision=='ABSTAIN'  # 1/4 Kelly < minimum 1 unit


def test_profit_lock_withdraws_principal_plus_four_percent_once():
    data=valid()
    risk=data.risk.model_copy(update={'free_cash':Decimal('1058')})
    updated, transfer=apply_profit_lock(risk)
    assert transfer==Decimal('1040') and updated.free_cash==Decimal('18')
    assert updated.phase=='PROFIT_ONLY' and updated.protected_cash==Decimal('1040')
    again, transfer2=apply_profit_lock(updated)
    assert transfer2==0 and again==updated


def test_no_profit_lock_under_threshold():
    original=valid().risk
    updated, transfer=apply_profit_lock(original)
    assert transfer==0 and updated==original


def test_negative_ev_abstains():
    data=valid(); m=data.model.model_copy(update={'player_a_probability':0.53,'player_a_prob_lower':0.51,'player_a_prob_upper':0.55})
    assert 'NO_CONSERVATIVE_EDGE' in evaluate(data.model_copy(update={'model':m})).reasons


def test_naive_datetime_is_rejected():
    data=valid().model_dump(); data['as_of']=T.replace(tzinfo=None)
    with pytest.raises(ValidationError):
        DecisionInput.model_validate(data)


def test_undeclared_post_match_feature_is_rejected():
    data=valid().model_dump(); data['features']['current_match_final_score']='6-3,6-2'
    with pytest.raises(ValidationError):
        DecisionInput.model_validate(data)


def test_same_player_rejected():
    data=valid().model_dump(); data['fixture']['player_b_id']=data['fixture']['player_a_id']
    with pytest.raises(ValidationError):
        DecisionInput.model_validate(data)


def test_wta_match_rejected():
    data=valid().model_dump(); data['fixture']['tour']='WTA'
    with pytest.raises(ValidationError):
        DecisionInput.model_validate(data)


def test_inconsistent_surface_format_rejected():
    data=valid().model_dump(); data['fixture']['best_of']=3
    with pytest.raises(ValidationError):
        DecisionInput.model_validate(data)


def test_odds_attached_to_different_match_abstains():
    data=valid(); odds=data.odds.model_copy(update={'match_id':'other-fixture'})
    assert 'MATCH_ID_CONFLICT' in evaluate(data.model_copy(update={'odds':odds})).reasons

def test_odds_player_order_reversed_abstains():
    data=valid(); odds=data.odds.model_copy(update={'player_a_id':'ATP-B-200','player_b_id':'ATP-A-100'})
    assert 'PLAYER_ODDS_ALIGNMENT_CONFLICT' in evaluate(data.model_copy(update={'odds':odds})).reasons

def test_prediction_model_for_different_match_abstains():
    data=valid(); model=data.model.model_copy(update={'match_id':'other-fixture'})
    assert 'MATCH_ID_CONFLICT' in evaluate(data.model_copy(update={'model':model})).reasons

def test_predicted_before_feature_snapshot_is_invalid():
    data=valid(); model=data.model.model_copy(update={'predicted_at':T-timedelta(minutes=20)})
    assert 'PREDICTION_BEFORE_FEATURES' in evaluate(data.model_copy(update={'model':model})).reasons

def test_profit_lock_cannot_be_bypassed_at_1050():
    data=valid(); risk=data.risk.model_copy(update={'free_cash':Decimal('1050')})
    assert 'PROFIT_LOCK_PENDING' in evaluate(data.model_copy(update={'risk':risk})).reasons

def test_profit_lock_cannot_steal_unsettled_capital():
    data=valid();risk=data.risk.model_copy(update={'free_cash':Decimal('1050'), 'open_exposure':Decimal('10')})
    new,transfer=apply_profit_lock(risk)
    assert transfer==0 and new==risk

def test_thin_player_history_abstains():
    data=valid(); f=data.features.model_copy(update={'history_n_a':5})
    assert 'THIN_PLAYER_HISTORY' in evaluate(data.model_copy(update={'features':f})).reasons

def test_future_published_schedule_abstains():
    data=valid(); f=data.fixture.model_copy(update={'schedule_published_at':T+timedelta(seconds=1)})
    assert 'SCHEDULE_NOT_ASOF' in evaluate(data.model_copy(update={'fixture':f})).reasons

def test_negative_quote_rate_rejected_by_contract():
    data=valid().model_dump();data['odds']['decimal_odds_a']=Decimal('-1.2')
    with pytest.raises(ValidationError): DecisionInput.model_validate(data)

def test_missing_model_date_metadata_rejected_by_contract():
    data=valid().model_dump();del data['model']['trained_until']
    with pytest.raises(ValidationError):DecisionInput.model_validate(data)


def test_external_model_self_certification_is_not_trusted():
    data=valid()
    ans=_evaluate(data)
    assert 'UNTRUSTED_VALIDATION_REPORT' in ans.reasons
    assert ans.stake==0

def test_wrong_validation_hash_is_not_trusted():
    data=valid();m=data.model.model_copy(update={'validation_report_sha256':'b'*64})
    assert 'UNTRUSTED_VALIDATION_REPORT' in evaluate(data.model_copy(update={'model':m})).reasons

def test_ledger_month_is_vietnam_local_not_utc():
    data=valid()
    ref=datetime(2027,1,31,20,0,tzinfo=UTC) # 2027-02-01 03:00 in Hanoi
    risk=data.risk.model_copy(update={'month':'2027-02'})
    ans=evaluate(data.model_copy(update={'as_of':ref,'risk':risk}))
    assert 'LEDGER_MONTH_MISMATCH' not in ans.reasons


def test_missing_serve_profile_excluded():
    data=valid();v=data.features.vector.model_copy(update={'spw_diff':None})
    features=data.features.model_copy(update={'vector':v})
    assert 'INCOMPLETE_FEATURE_VECTOR' in evaluate(data.model_copy(update={'features':features})).reasons

def test_future_surface_mismatch_excluded():
    data=valid();v=data.features.vector.model_copy(update={'surface_clay':1})
    features=data.features.model_copy(update={'vector':v})
    assert 'FEATURE_SURFACE_CONFLICT' in evaluate(data.model_copy(update={'features':features})).reasons

def test_imputed_rankings_excluded():
    data=valid();features=data.features.model_copy(update={'imputed_fields':['rank_diff']})
    assert 'IMPUTED_CRITICAL_FEATURE' in evaluate(data.model_copy(update={'features':features})).reasons

def test_missing_feature_vector_field_fails_contract():
    data=valid().model_dump(); del data['features']['vector']['rank_diff']
    with pytest.raises(ValidationError): DecisionInput.model_validate(data)
