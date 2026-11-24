"""P0 cross-month paper-only settlements: cost-basis asset carry, no backdating."""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from atp_gate.contracts import RiskState, DecisionOutput
from atp_gate.paper_ledger import (
    PaperBook, close_month, reconcile_periods, record_selection, settle_selection,
)

UTC = timezone.utc


def instant(year, month, day, hour, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


def new_book(month: str, at: datetime):
    state = RiskState(
        month=month, free_cash=Decimal("1000"), protected_cash=Decimal("0"),
        open_exposure=Decimal("0"), phase="NORMAL", selections_today=0,
        week_loss_realized=Decimal("0"), month_loss_realized=Decimal("0"),
        annual_negative_month_loss=Decimal("0"), seen_match_ids=[],
    )
    return reconcile_periods(PaperBook(risk=state), at)


def selection(stake="10"):
    return DecisionOutput(
        decision="SELECT", side="A", stake=Decimal(stake),
        ev_lower=0.05, p_lower=0.6, market_probability=0.5, reasons=[],
    )


@pytest.mark.parametrize("outcome,free_after,month_net,loss_week", [
    ("WIN", "1009.00", "9.00", "0"),
    ("LOSS", "990.00", "-10.00", "10"),
    ("VOID", "1000.00", "0.00", "0"),
])
def test_new_month_settlement_counts_only_in_settlement_month(
    outcome, free_after, month_net, loss_week,
):
    # Jan 31 16:50 UTC is Jan 31 23:50 in Bangkok.
    before = instant(2027, 1, 31, 16, 50)
    after = instant(2027, 1, 31, 17, 10)  # Feb 1 00:10 Bangkok
    old = record_selection(new_book("2027-01", before), "m-cross", selection(),
                           Decimal("1.90"), before)
    carried, january = close_month(old, "2027-02")
    assert january.net == Decimal("0")
    assert january.needed_topup == Decimal("0")
    assert january.carried_open_exposure == Decimal("10")
    assert carried.risk.free_cash == Decimal("990")
    assert carried.risk.open_exposure == Decimal("10")
    assert carried.risk.selection_day == date(2027, 2, 1)
    assert carried.risk.loss_week_start == date(2027, 2, 1)
    assert carried.open_positions["m-cross"].placed_at == before
    assert len(carried.journal) == 1

    final = settle_selection(carried, "m-cross", outcome, after)
    assert final.risk.free_cash == Decimal(free_after)
    assert final.risk.open_exposure == Decimal("0")
    assert final.risk.month_loss_realized == Decimal("10") if outcome == "LOSS" else final.risk.month_loss_realized == 0
    assert final.risk.week_loss_realized == Decimal(loss_week)
    march, february = close_month(final, "2027-03")
    assert february.net == Decimal(month_net)
    assert february.needed_topup == (Decimal("10") if outcome == "LOSS" else Decimal("0"))
    assert february.carried_open_exposure == Decimal("0")
    assert march.risk.open_exposure == 0


def test_two_positions_and_prior_realized_loss_do_not_double_count():
    # One January loss is realized; one position is pending at boundary.
    before = instant(2027, 1, 31, 16, 45)
    book = new_book("2027-01", before)
    book = record_selection(book, "settled", selection(), Decimal("1.90"), before)
    book = record_selection(book, "pending", selection(), Decimal("1.90"),
                            instant(2027, 1, 31, 16, 46))
    book = settle_selection(book, "settled", "LOSS",
                            instant(2027, 1, 31, 16, 48))
    assert book.risk.free_cash == Decimal("980")
    assert book.risk.open_exposure == Decimal("10")

    carried, january = close_month(book, "2027-02")
    assert january.net == Decimal("-10")
    assert january.needed_topup == Decimal("10")
    assert january.carried_open_exposure == Decimal("10")
    assert carried.risk.free_cash == Decimal("990")
    assert carried.risk.open_exposure == Decimal("10")
    assert carried.risk.annual_negative_month_loss == Decimal("10")
    assert len(carried.journal) == 3

    settled = settle_selection(carried, "pending", "WIN",
                               instant(2027, 1, 31, 17, 12))
    _, february = close_month(settled, "2027-03")
    assert february.net == Decimal("9")
    assert february.needed_topup == 0


def test_new_year_carry_defers_realized_loss_until_new_year():
    before = instant(2026, 12, 31, 16, 50)
    book = record_selection(new_book("2026-12", before), "new-year", selection(),
                            Decimal("1.90"), before)
    carried, december = close_month(book, "2027-01")
    assert december.net == Decimal("0")
    assert carried.risk.annual_negative_month_loss == Decimal("0")
    assert carried.risk.loss_week_start == date(2026, 12, 28)
    settled = settle_selection(carried, "new-year", "LOSS",
                               instant(2026, 12, 31, 17, 10))
    assert settled.risk.week_loss_realized == Decimal("10")
    feb_book, january = close_month(settled, "2027-02")
    assert january.net == Decimal("-10")
    assert feb_book.risk.annual_negative_month_loss == Decimal("10")


def test_settlement_cannot_be_backdated_into_already_closed_month():
    before = instant(2027, 1, 31, 16, 50)
    book = record_selection(new_book("2027-01", before), "never-backdate",
                            selection(), Decimal("1.90"), before)
    next_book, _ = close_month(book, "2027-02")
    with pytest.raises(ValueError, match="month mismatch"):
        settle_selection(next_book, "never-backdate", "LOSS",
                         instant(2027, 1, 31, 16, 55))


def test_close_rejects_open_exposure_mismatch_even_on_month_border():
    before = instant(2027, 1, 31, 16, 50)
    book = record_selection(new_book("2027-01", before), "m-bad", selection(),
                            Decimal("1.90"), before)
    corrupt = book.model_copy(update={
        "risk": book.risk.model_copy(update={"open_exposure": Decimal("11")})
    })
    with pytest.raises(ValueError, match="exposure"):
        close_month(corrupt, "2027-02")
