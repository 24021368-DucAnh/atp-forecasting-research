"""Deterministic PAPER-ONLY model evidence, selection and stake gate.

Input comes from source adapters + a separate, independently validated model.
This module does not request live prices or place financial transactions.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal, ROUND_DOWN
from collections.abc import Mapping
from zoneinfo import ZoneInfo
from .contracts import DecisionInput, DecisionOutput, RiskState
from .feature_schema import FEATURE_SCHEMA_HASH

X = Decimal("1000")
CENT = Decimal("0.01")
MIN_STAKE = Decimal("1.00")  # research-unit threshold (not platform minimum)
MONTHLY_FLOOR = Decimal("950")
WEEKLY_LOSS_MAX = Decimal("30")
ANNUAL_NEGATIVE_MONTH_MAX = Decimal("200")
MAX_OPEN = Decimal("20")
MAX_STAKE = Decimal("10")
MIN_EV = 0.02
MAX_QUOTE_AGE = timedelta(minutes=30)
MAX_MODEL_AGE = timedelta(minutes=30)
MAX_SCHEDULE_AGE = timedelta(hours=6)
CUTOFF = timedelta(minutes=60)


def apply_profit_lock(risk: RiskState) -> tuple[RiskState, Decimal]:
    """Lock X+4% on reaching X+5%, once, only with no unsettled exposure.

    State transition should be called after settlement, not while bets are open.
    """
    if risk.phase != "NORMAL" or risk.open_exposure != 0 or risk.free_cash < Decimal("1050"):
        return risk, Decimal("0")
    transfer = Decimal("1040")
    updated = risk.model_copy(update={
        "free_cash": risk.free_cash - transfer,
        "protected_cash": risk.protected_cash + transfer,
        "phase": "PROFIT_ONLY",
    })
    return updated, transfer


def _abstain(reasons: list[str], ev_lower=None, p_lower=None, market_probability=None) -> DecisionOutput:
    return DecisionOutput(decision="ABSTAIN", side=None, stake=Decimal("0"),
                          ev_lower=ev_lower, p_lower=p_lower, market_probability=market_probability,
                          reasons=sorted(set(reasons)))


def evaluate(data: DecisionInput, *, trusted_validation_reports: Mapping[str, str] | None = None) -> DecisionOutput:
    """Return a hypothetical allocation only when every prerequisite passes.

    Matching historical closing odds or training-date approximations are NOT valid
    evidence of a tradable price at T-60 minutes. Caller must also verify source
    authenticity and the validator-signed report provenance before calling this.
    """
    t, f, o, snap, m, r = data.as_of, data.fixture, data.odds, data.features, data.model, data.risk
    reasons: list[str] = []
    if not (f.match_id == o.match_id == snap.match_id == m.match_id):
        reasons.append("MATCH_ID_CONFLICT")
    if (f.player_a_id, f.player_b_id) != (o.player_a_id, o.player_b_id):
        reasons.append("PLAYER_ODDS_ALIGNMENT_CONFLICT")
    if snap.history_n_a < 10 or snap.history_n_b < 10:
        reasons.append("THIN_PLAYER_HISTORY")
    if m.predicted_at < snap.built_at:
        reasons.append("PREDICTION_BEFORE_FEATURES")
    if r.phase == "NORMAL" and r.free_cash >= Decimal("1050") and r.open_exposure == 0:
        reasons.append("PROFIT_LOCK_PENDING")
    if f.status not in ("SCHEDULED", "DELAYED"):
        reasons.append("NOT_PREMATCH")
    if not f.start_confirmed:
        reasons.append("START_UNCONFIRMED")
    if f.scheduled_start - t < CUTOFF:
        reasons.append("INSIDE_PREDICTION_CUTOFF")
    if f.schedule_published_at > t or f.schedule_observed_at > t or f.schedule_observed_at < f.schedule_published_at:
        reasons.append("SCHEDULE_NOT_ASOF")
    elif t - f.schedule_observed_at > MAX_SCHEDULE_AGE:
        reasons.append("SCHEDULE_STALE")
    if o.observed_at > t or o.published_at > t or o.retrieved_at > t or o.observed_at < o.published_at or o.retrieved_at < o.observed_at:
        reasons.append("QUOTE_NOT_ASOF")
    elif t - o.observed_at > MAX_QUOTE_AGE:
        reasons.append("QUOTE_STALE")
    if o.settlement_rule == "UNKNOWN":
        reasons.append("SETTLEMENT_RULE_UNKNOWN")
    if snap.built_at > t or snap.data_asof > t or snap.built_at < snap.data_asof:
        reasons.append("FEATURES_NOT_ASOF")
    if snap.critical_missing:
        reasons.append("CRITICAL_FEATURE_MISSING")
    if not snap.matched_player_ids or snap.duplicate_match_count != 1:
        reasons.append("AMBIGUOUS_MATCH")
    if not snap.match_time_precise:
        reasons.append("IMPRECISE_MATCH_TIME")
    if not snap.source_license_ok:
        reasons.append("UNVERIFIED_DATA_RIGHTS")
    if not snap.source_reconciliation_ok:
        reasons.append("SOURCE_CONFLICT")
    if snap.vector.has_missing_profile():
        reasons.append("INCOMPLETE_FEATURE_VECTOR")
    if snap.imputed_fields:
        reasons.append("IMPUTED_CRITICAL_FEATURE")
    if snap.vector.min_nm != min(snap.history_n_a, snap.history_n_b):
        reasons.append("FEATURE_HISTORY_CONFLICT")
    if (snap.vector.surface_clay != int(f.surface == "CLAY")
            or snap.vector.surface_grass != int(f.surface == "GRASS")):
        reasons.append("FEATURE_SURFACE_CONFLICT")
    if (snap.feature_schema_hash != m.feature_schema_hash
            or snap.feature_schema_hash != FEATURE_SCHEMA_HASH):
        reasons.append("FEATURE_SCHEMA_MISMATCH")
    if not (m.trained_until < m.calibrated_from <= m.calibrated_until <= m.validated_until < m.released_at <= t):
        reasons.append("MODEL_NOT_ASOF")
    if m.predicted_at < m.released_at or m.predicted_at > t or t - m.predicted_at > MAX_MODEL_AGE:
        reasons.append("PREDICTION_NOT_ASOF")
    if not m.calibration_verified or m.validation_n < 300:
        reasons.append("CALIBRATION_NOT_VERIFIED")
    if not m.market_edge_verified or m.selected_n < 100:
        reasons.append("EDGE_NOT_VERIFIED")
    trusted_validation_reports = trusted_validation_reports or {}
    if trusted_validation_reports.get(m.validation_report_id) != m.validation_report_sha256:
        reasons.append("UNTRUSTED_VALIDATION_REPORT")
    if r.month != t.astimezone(ZoneInfo("Asia/Bangkok")).strftime("%Y-%m"):
        reasons.append("LEDGER_MONTH_MISMATCH")
    if f.match_id in r.seen_match_ids:
        reasons.append("DUPLICATE_SELECTION")
    if r.phase == "STOPPED":
        reasons.append("STOPPED")
    if r.selections_today >= 2:
        reasons.append("DAILY_LIMIT_REACHED")
    if r.week_loss_realized >= WEEKLY_LOSS_MAX or r.annual_negative_month_loss >= ANNUAL_NEGATIVE_MONTH_MAX:
        reasons.append("RISK_LIMIT_REACHED")
    if r.phase == "NORMAL" and r.free_cash <= MONTHLY_FLOOR:
        reasons.append("RISK_LIMIT_REACHED")
    if r.open_exposure >= MAX_OPEN:
        reasons.append("RISK_LIMIT_REACHED")
    if reasons:
        return _abstain(reasons)

    pa_lo = m.player_a_prob_lower
    pb_lo = 1.0 - m.player_a_prob_upper
    sides = [("A", pa_lo, float(o.decimal_odds_a)), ("B", pb_lo, float(o.decimal_odds_b))]
    candidate = max(sides, key=lambda x: x[1] * x[2] - 1.0)
    side, p_lower, odds = candidate
    ev = p_lower * odds - 1.0
    market_p = (1.0 / odds) / (1.0 / float(o.decimal_odds_a) + 1.0 / float(o.decimal_odds_b))
    if ev <= MIN_EV:
        return _abstain(["NO_CONSERVATIVE_EDGE"], ev_lower=ev, p_lower=p_lower,
                        market_probability=market_p)
    f_kelly = max(0.0, ev / (odds - 1.0))
    kelly_stake = Decimal(str(0.25 * f_kelly)) * min(r.free_cash, X)
    monthly_left = max(Decimal("0"), r.free_cash - MONTHLY_FLOOR) if r.phase == "NORMAL" else r.free_cash
    week_left = max(Decimal("0"), WEEKLY_LOSS_MAX - r.week_loss_realized - r.open_exposure)
    year_left = max(Decimal("0"), ANNUAL_NEGATIVE_MONTH_MAX - r.annual_negative_month_loss - r.open_exposure)
    open_left = max(Decimal("0"), MAX_OPEN - r.open_exposure)
    profit_only_left = r.free_cash * Decimal("0.20") if r.phase == "PROFIT_ONLY" else MAX_STAKE
    stake = max(Decimal("0"), min(kelly_stake, MAX_STAKE, monthly_left,
                                  week_left, year_left, open_left, profit_only_left, r.free_cash))
    stake = stake.quantize(CENT, rounding=ROUND_DOWN)
    if stake < MIN_STAKE:
        return _abstain(["RISK_LIMIT_REACHED"], ev_lower=ev, p_lower=p_lower,
                        market_probability=market_p)
    return DecisionOutput(decision="SELECT", side=side, stake=stake, ev_lower=ev,
                          p_lower=p_lower, market_probability=market_p, reasons=[])
