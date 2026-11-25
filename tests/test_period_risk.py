"""Regression contracts for evidence-derived daily/weekly paper-risk periods.

Every asserted expected date or amount is calculated by hand.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from atp_gate.contracts import RiskState, DecisionOutput
from atp_gate.paper_ledger import (
    JournalEvent, PaperBook, reconcile_periods, record_selection, settle_selection, close_month,
)
from atp_gate.period_risk import period_keys, replay_journal

UTC = timezone.utc


def at(y, m, d, h=0, minute=0):
    return datetime(y, m, d, h, minute, tzinfo=UTC)


def risk(*, month="2027-01", free_cash="1000"):
    return RiskState(
        month=month, free_cash=Decimal(free_cash), open_exposure=0,
        protected_cash=0, phase="NORMAL", selections_today=0,
        week_loss_realized=0, month_loss_realized=0,
        annual_negative_month_loss=0, seen_match_ids=[],
    )


def decision():
    return DecisionOutput(
        decision="SELECT", side="A", stake=Decimal("10"),
        ev_lower=0.05, p_lower=0.6, market_probability=0.5, reasons=[],
    )


def test_bangkok_day_and_monday_week_cross_utc_midnight():
    assert period_keys(at(2027, 1, 3, 16, 59)) == (date(2027, 1, 3), date(2026, 12, 28))
    assert period_keys(at(2027, 1, 3, 17, 0)) == (date(2027, 1, 4), date(2027, 1, 4))
    # Month boundary on a Thursday is NOT a new week.
    assert period_keys(at(2027, 3, 31, 17, 0)) == (date(2027, 4, 1), date(2027, 3, 29))


def test_replay_counts_reserve_day_and_loss_settlement_week():
    friday = at(2027, 1, 8, 12)
    monday = at(2027, 1, 11, 12)
    events = [
        JournalEvent(match_id="m-1", event="RESERVE", amount=Decimal("10"), at=friday),
        JournalEvent(match_id="m-1", event="SETTLE_LOSS", amount=Decimal("0"), at=monday),
    ]
    summary = replay_journal(events, monday)
    assert summary.daily_counts[date(2027, 1, 8)] == 1
    assert summary.weekly_losses[date(2027, 1, 11)] == Decimal("10")
    assert summary.weekly_losses.get(date(2027, 1, 4), 0) == 0
    assert summary.open_stakes == {}


@pytest.mark.parametrize("events", [
    [("SETTLE_LOSS", "m-1", "0", 1)],
    [("RESERVE", "m-1", "10", 1), ("RESERVE", "m-1", "10", 2)],
    [("RESERVE", "m-1", "10", 1), ("SETTLE_LOSS", "m-1", "0", 2), ("SETTLE_LOSS", "m-1", "0", 3)],
    [("RESERVE", "m-1", "10", 2), ("SETTLE_LOSS", "m-1", "0", 1)],
    [("RESERVE", "m-1", "10", 1), ("SETTLE_LOSS", "m-1", "5", 2)],
])
def test_replay_rejects_invalid_or_forged_journal(events):
    rows = [JournalEvent(match_id=ident, event=event, amount=Decimal(amount),
                         at=at(2027, 1, 20, 9) + timedelta(minutes=mins))
            for event, ident, amount, mins in events]
    with pytest.raises(ValueError):
        replay_journal(rows, at(2027, 1, 21))


def test_replay_rejects_future_entry():
    rows = [JournalEvent(match_id="m-1", event="RESERVE", amount=Decimal("10"),
                         at=at(2027, 1, 20, 10))]
    with pytest.raises(ValueError):
        replay_journal(rows, at(2027, 1, 20, 9))


def test_day_rollover_requires_replay_and_preserves_positions():
    # Local Jan 21 starts at Jan 20 17:00 UTC.
    t = at(2027, 1, 20, 16, 55)
    book = reconcile_periods(PaperBook(risk=risk()), t)
    book = record_selection(book, "m-1", decision(), Decimal("1.90"), t)
    book = record_selection(book, "m-2", decision(), Decimal("1.90"), t + timedelta(minutes=1))
    assert book.risk.selections_today == 2
    with pytest.raises(ValueError):
        record_selection(book, "m-3", decision(), Decimal("1.90"), t + timedelta(minutes=2))
    nxt = reconcile_periods(book, t + timedelta(minutes=5))
    assert nxt.risk.selections_today == 0
    assert nxt.risk.open_exposure == Decimal("20")
    assert nxt.risk.selection_day == date(2027, 1, 21)
    assert len(nxt.open_positions) == 2


def test_weekly_loss_rollover_and_old_week_loss_preservation():
    sunday = at(2027, 1, 3, 16, 50)  # Bangkok Sun Jan 3 23:50
    book = reconcile_periods(PaperBook(risk=risk()), sunday)
    book = record_selection(book, "m-1", decision(), Decimal("1.90"), sunday)
    book = settle_selection(book, "m-1", "LOSS", sunday + timedelta(minutes=2))
    assert book.risk.week_loss_realized == Decimal("10")
    monday = reconcile_periods(book, sunday + timedelta(minutes=15))
    assert monday.risk.loss_week_start == date(2027, 1, 4)
    assert monday.risk.week_loss_realized == 0


def test_close_month_retains_same_week_loss():
    t = at(2027, 3, 31, 15)  # Bangkok Mar 31 22:00, Wednesday
    book = reconcile_periods(PaperBook(risk=risk(month="2027-03")), t)
    book = record_selection(book, "m-1", decision(), Decimal("1.90"), t)
    book = settle_selection(book, "m-1", "LOSS", t + timedelta(minutes=10))
    next_book, report = close_month(book, "2027-04")
    assert report.net == Decimal("-10")
    assert next_book.risk.selection_day == date(2027, 4, 1)
    assert next_book.risk.loss_week_start == date(2027, 3, 29)
    assert next_book.risk.week_loss_realized == Decimal("10")
    assert len(next_book.journal) == 2


def test_old_period_counter_mismatch_fails_instead_of_resetting():
    t = at(2027, 1, 20, 9)
    book = reconcile_periods(PaperBook(risk=risk()), t)
    book = record_selection(book, "m-1", decision(), Decimal("1.90"), t)
    forged = book.model_copy(update={"risk": book.risk.model_copy(update={"selections_today": 0})})
    with pytest.raises(ValueError):
        reconcile_periods(forged, t + timedelta(days=1))


def test_unstamped_nonempty_legacy_book_cannot_reconcile():
    t = at(2027, 1, 20, 9)
    book = PaperBook(risk=risk(), journal=[
        JournalEvent(match_id="m-1", event="RESERVE", amount=Decimal("10"), at=t)
    ])
    with pytest.raises(ValueError):
        reconcile_periods(book, t + timedelta(minutes=1))


def test_cross_month_unsettled_settlement_fails_closed():
    t = at(2027, 1, 31, 16, 50)  # Bangkok Jan 31 23:50
    book = reconcile_periods(PaperBook(risk=risk()), t)
    book = record_selection(book, "m-1", decision(), Decimal("1.90"), t)
    with pytest.raises(ValueError):
        settle_selection(book, "m-1", "LOSS", at(2027, 1, 31, 17, 10))
