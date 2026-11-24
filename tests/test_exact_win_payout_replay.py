"""P0 #25a: reserved accepted odds must independently justify WIN payouts.

All values are synthetic paper-only accounting examples.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from atp_gate.contracts import DecisionOutput, RiskState
from atp_gate.paper_ledger import (
    JournalEvent, PaperBook, reconcile_periods, record_selection, settle_selection,
)
from atp_gate.period_risk import replay_journal


T = datetime(2027, 1, 20, 9, tzinfo=timezone.utc)


def book():
    state = RiskState(
        month="2027-01", free_cash=Decimal("1000"),
        open_exposure=Decimal("0"), protected_cash=Decimal("0"),
        phase="NORMAL", selections_today=0, month_loss_realized=0,
        week_loss_realized=0, annual_negative_month_loss=0, seen_match_ids=[],
    )
    return PaperBook(risk=state)


def decision():
    return DecisionOutput(
        decision="SELECT", side="A", stake=Decimal("10"),
        ev_lower=0.05, p_lower=0.6, market_probability=0.5, reasons=[],
    )


def placed():
    return record_selection(book(), "synthetic-1", decision(), Decimal("1.90"), T)


def test_reserve_evidence_captures_accepted_side_and_odds():
    result = placed()
    reserve = result.journal[0]
    assert reserve.event == "RESERVE"
    assert reserve.amount == Decimal("10")
    assert getattr(reserve, "side", None) == "A"
    assert getattr(reserve, "odds", None) == Decimal("1.90")


def test_replay_rejects_win_payment_inconsistent_with_original_accepted_odds():
    winner = settle_selection(placed(), "synthetic-1", "WIN", T + timedelta(hours=1))
    assert winner.journal[1].amount == Decimal("19.00")
    forged = list(winner.journal)
    forged[1] = forged[1].model_copy(update={"amount": Decimal("20.00")})
    with pytest.raises(ValueError, match="payout|odds|WIN"):
        replay_journal(forged, T + timedelta(hours=2))


def test_replay_verifies_correct_win_payout_and_original_price():
    winner = settle_selection(placed(), "synthetic-1", "WIN", T + timedelta(hours=1))
    verified = replay_journal(winner.journal, T + timedelta(hours=2))
    assert verified.open_stakes == {}
    assert verified.reserve_odds["synthetic-1"] == Decimal("1.90")
    assert verified.reserve_sides["synthetic-1"] == "A"


def test_reconcile_refuses_open_position_with_forged_odds():
    original = placed()
    position = original.open_positions["synthetic-1"]
    forged_position = position.model_copy(update={"odds": Decimal("2.00")})
    modified = original.model_copy(update={
        "open_positions": {"synthetic-1": forged_position}
    })
    with pytest.raises(ValueError, match="odds|price|journal"):
        reconcile_periods(modified, T + timedelta(minutes=5))


def test_reconcile_refuses_open_position_with_forged_side():
    original = placed()
    position = original.open_positions["synthetic-1"]
    changed = original.model_copy(update={
        "open_positions": {"synthetic-1": position.model_copy(update={"side": "B"})}
    })
    with pytest.raises(ValueError, match="side|journal|identity"):
        reconcile_periods(changed, T + timedelta(minutes=5))


def test_legacy_reserve_without_original_odds_does_not_certify_win():
    legacy = [
        JournalEvent(match_id="old", event="RESERVE", amount=Decimal("10"), at=T),
        JournalEvent(match_id="old", event="SETTLE_WIN",
                     amount=Decimal("19"), at=T + timedelta(minutes=10)),
    ]
    with pytest.raises(ValueError, match="odds|price|reserve"):
        replay_journal(legacy, T + timedelta(hours=1))


def test_legacy_reserve_remains_usable_for_loss_and_void_period_count():
    old_loss = [
        JournalEvent(match_id="old", event="RESERVE", amount=Decimal("10"), at=T),
        JournalEvent(match_id="old", event="SETTLE_LOSS",
                     amount=Decimal("0"), at=T + timedelta(minutes=1)),
    ]
    result = replay_journal(old_loss, T + timedelta(minutes=2))
    assert result.weekly_losses
    old_void = [
        JournalEvent(match_id="old", event="RESERVE", amount=Decimal("10"), at=T),
        JournalEvent(match_id="old", event="SETTLE_VOID",
                     amount=Decimal("10"), at=T + timedelta(minutes=1)),
    ]
    assert replay_journal(old_void, T + timedelta(minutes=2)).open_stakes == {}


def test_nonfinite_accepted_price_is_rejected_before_reserve():
    for value in (Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")):
        with pytest.raises(ValueError, match="odds|price|finite|decimal"):
            record_selection(book(), "synthetic-bad", decision(), value, T)


def test_settlement_event_cannot_inject_a_second_accepted_price():
    correct = settle_selection(placed(), "synthetic-1", "WIN", T + timedelta(minutes=10))
    forged = list(correct.journal)
    forged[1] = forged[1].model_copy(update={"odds": Decimal("1.90")})
    with pytest.raises(ValueError, match="settlement|odds|price"):
        replay_journal(forged, T + timedelta(minutes=15))


def test_replay_rejects_partial_reserve_quote_without_accepted_side():
    rows = [
        JournalEvent(match_id="missing-side", event="RESERVE",
                     amount=Decimal("10"), odds=Decimal("1.90"), at=T),
        JournalEvent(match_id="missing-side", event="SETTLE_WIN",
                     amount=Decimal("19.00"), at=T + timedelta(minutes=1)),
    ]
    with pytest.raises(ValueError, match="side|reserve|quote"):
        replay_journal(rows, T + timedelta(minutes=2))


def test_replay_rejects_reserve_with_mutated_invalid_side():
    rows = [
        JournalEvent(match_id="invalid-side", event="RESERVE",
                     amount=Decimal("10"), side="A",
                     odds=Decimal("1.90"), at=T),
        JournalEvent(match_id="invalid-side", event="SETTLE_WIN",
                     amount=Decimal("19.00"), at=T + timedelta(minutes=1)),
    ]
    forged = list(rows)
    forged[0] = forged[0].model_copy(update={"side": "C"})
    with pytest.raises(ValueError, match="side|reserve|quote"):
        replay_journal(forged, T + timedelta(minutes=2))
