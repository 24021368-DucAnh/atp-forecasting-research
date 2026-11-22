"""Fail-closed, timezone-aware contracts for ATP pre-match evidence.

All normalized IDs and market timestamps originate from *trusted* upstream adapters.
A valid contract does NOT itself establish source authenticity or model profitability.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator
from .feature_schema import FeatureVector


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Fixture(StrictModel):
    match_id: str = Field(min_length=5)
    event_id: str = Field(min_length=3)
    player_a_id: str = Field(min_length=3)
    player_b_id: str = Field(min_length=3)
    competition: Literal["GRAND_SLAM", "MASTERS_1000", "ATP_500"]
    draw: Literal["MAIN"]
    tour: Literal["ATP"]
    gender: Literal["MEN"]
    discipline: Literal["SINGLES"]
    surface: Literal["HARD", "CLAY", "GRASS"]
    best_of: Literal[3, 5]
    round: Literal["R128", "R64", "R32", "R16", "QF", "SF", "F"]
    status: Literal["SCHEDULED", "DELAYED", "STARTED", "COMPLETED", "WALKOVER", "CANCELLED"]
    start_confirmed: bool
    scheduled_start: AwareDatetime
    schedule_published_at: AwareDatetime
    schedule_observed_at: AwareDatetime
    schedule_source: str = Field(min_length=3)

    @model_validator(mode="after")
    def check_identity_and_format(self):
        if self.player_a_id == self.player_b_id:
            raise ValueError("player IDs must be distinct")
        expected = 5 if self.competition == "GRAND_SLAM" else 3
        if self.best_of != expected:
            raise ValueError("unsupported best-of format for competition")
        return self


class OddsQuote(StrictModel):
    match_id: str = Field(min_length=5)
    player_a_id: str = Field(min_length=3)
    player_b_id: str = Field(min_length=3)
    market: Literal["MATCH_WINNER"]
    bookmaker: str = Field(min_length=2)
    source_id: str = Field(min_length=3)
    decimal_odds_a: Decimal = Field(gt=Decimal("1"), le=Decimal("1000"))
    decimal_odds_b: Decimal = Field(gt=Decimal("1"), le=Decimal("1000"))
    observed_at: AwareDatetime
    published_at: AwareDatetime
    retrieved_at: AwareDatetime
    settlement_rule: Literal["RETIREMENT_ACTION", "RETIREMENT_VOID", "UNKNOWN"]

    @model_validator(mode="after")
    def check_pair(self):
        overround = Decimal("1") / self.decimal_odds_a + Decimal("1") / self.decimal_odds_b
        if not Decimal("0.90") <= overround <= Decimal("1.35"):
            raise ValueError("implausible bookmaker overround; review odds pairing")
        return self


class FeatureSnapshot(StrictModel):
    match_id: str = Field(min_length=5)
    history_n_a: int = Field(default=10, ge=0)
    history_n_b: int = Field(default=10, ge=0)
    built_at: AwareDatetime
    data_asof: AwareDatetime
    feature_schema_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    vector: FeatureVector
    imputed_fields: list[str] = Field(default_factory=list)
    critical_missing: list[str] = Field(default_factory=list)
    matched_player_ids: bool
    duplicate_match_count: int = Field(ge=0)
    match_time_precise: bool
    source_license_ok: bool
    source_reconciliation_ok: bool


class ModelEvidence(StrictModel):
    match_id: str = Field(min_length=5)
    model_id: str = Field(min_length=3)
    trained_until: AwareDatetime
    calibrated_from: AwareDatetime
    calibrated_until: AwareDatetime
    validated_until: AwareDatetime
    released_at: AwareDatetime
    predicted_at: AwareDatetime
    feature_schema_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    player_a_probability: float = Field(gt=0.0, lt=1.0)
    player_a_prob_lower: float = Field(ge=0.0, le=1.0)
    player_a_prob_upper: float = Field(ge=0.0, le=1.0)
    validation_report_id: str = Field(min_length=3)
    validation_report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    market_edge_verified: bool
    calibration_verified: bool
    validation_n: int = Field(ge=0)
    selected_n: int = Field(ge=0)

    @model_validator(mode="after")
    def check_intervals(self):
        if not self.player_a_prob_lower <= self.player_a_probability <= self.player_a_prob_upper:
            raise ValueError("probability must fall inside its validation interval")
        return self


class RiskState(StrictModel):
    month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    free_cash: Decimal = Field(ge=Decimal("0"))
    open_exposure: Decimal = Field(ge=Decimal("0"))
    protected_cash: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    phase: Literal["NORMAL", "PROFIT_ONLY", "STOPPED"]
    selections_today: int = Field(ge=0)
    month_loss_realized: Decimal = Field(ge=Decimal("0"))
    week_loss_realized: Decimal = Field(ge=Decimal("0"))
    annual_negative_month_loss: Decimal = Field(ge=Decimal("0"))
    seen_match_ids: list[str] = Field(default_factory=list)


class DecisionInput(StrictModel):
    as_of: AwareDatetime
    fixture: Fixture
    odds: OddsQuote
    features: FeatureSnapshot
    model: ModelEvidence
    risk: RiskState


class DecisionOutput(StrictModel):
    decision: Literal["SELECT", "ABSTAIN"]
    side: Literal["A", "B"] | None
    stake: Decimal
    ev_lower: float | None
    p_lower: float | None
    market_probability: float | None
    reasons: list[str]
    policy_version: str = "ATP_GATE_0.1"
