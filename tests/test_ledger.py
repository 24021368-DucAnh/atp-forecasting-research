from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest
from atp_gate.contracts import RiskState, DecisionOutput
from atp_gate.paper_ledger import PaperBook, record_selection, settle_selection, close_month

T=datetime(2027,1,20,9,tzinfo=timezone.utc)

def book(free='1000',protect='0'):
    return PaperBook(risk=RiskState(month='2027-01',free_cash=Decimal(free),open_exposure=0,
        protected_cash=Decimal(protect),phase='NORMAL',selections_today=0,
        month_loss_realized=0,week_loss_realized=0,annual_negative_month_loss=0,seen_match_ids=[]))

def selection():
    return DecisionOutput(decision='SELECT',side='A',stake=Decimal('10.00'),ev_lower=0.064,
                          p_lower=0.56,market_probability=0.519,reasons=[])


def test_order_reserves_cash_and_exposure():
    updated=record_selection(book(), 'fixture-1', selection(), Decimal('1.90'),T)
    assert updated.risk.free_cash==Decimal('990')
    assert updated.risk.open_exposure==Decimal('10')
    assert updated.risk.selections_today==1
    assert updated.risk.seen_match_ids==['fixture-1']
    assert 'fixture-1' in updated.open_positions


def test_won_order_returns_stake_and_profit():
    initial=record_selection(book(), 'fixture-1', selection(), Decimal('1.90'),T)
    done=settle_selection(initial,'fixture-1','WIN',T+timedelta(hours=2))
    assert done.risk.free_cash==Decimal('1009.00')
    assert done.risk.open_exposure==0
    assert len(done.journal)==2


def test_lost_order_debits_realized_loss_budget():
    initial=record_selection(book(),'fixture-1',selection(),Decimal('1.90'),T)
    done=settle_selection(initial,'fixture-1','LOSS',T+timedelta(hours=2))
    assert done.risk.free_cash==Decimal('990')
    assert done.risk.week_loss_realized==Decimal('10')
    assert done.risk.month_loss_realized==Decimal('10')


def test_void_order_refunds():
    initial=record_selection(book(),'fixture-1',selection(),Decimal('1.90'),T)
    done=settle_selection(initial,'fixture-1','VOID',T+timedelta(hours=2))
    assert done.risk.free_cash==Decimal('1000')
    assert done.risk.week_loss_realized==0


def test_no_duplicate_position():
    b=record_selection(book(),'fixture-1',selection(),Decimal('1.90'),T)
    with pytest.raises(ValueError,match='already'):
        record_selection(b,'fixture-1',selection(),Decimal('1.90'),T)


def test_invalid_settlement_twice_rejected():
    b=record_selection(book(),'fixture-1',selection(),Decimal('1.90'),T)
    b=settle_selection(b,'fixture-1','LOSS',T+timedelta(hours=2))
    with pytest.raises(ValueError,match='open'):
        settle_selection(b,'fixture-1','WIN',T+timedelta(hours=3))


def test_unsettled_risk_carries_cost_basis_through_month_rollover():
    b=record_selection(book(),'fixture-1',selection(),Decimal('1.90'),T)
    future, report=close_month(b,'2027-02')
    assert report.net == Decimal('0')
    assert report.carried_open_exposure == Decimal('10')
    assert future.risk.free_cash == Decimal('990')
    assert future.risk.open_exposure == Decimal('10')
    assert future.open_positions['fixture-1'].stake == Decimal('10')


def test_monthly_reset_counts_losses_as_external_replenishment():
    b=book('940')
    next_book,report=close_month(b,'2027-02')
    assert report.net==Decimal('-60')
    assert report.needed_topup==Decimal('60')
    assert next_book.risk.free_cash==Decimal('1000')
    assert next_book.risk.annual_negative_month_loss==Decimal('60')
    assert next_book.risk.protected_cash==0


def test_saved_principal_not_counted_as_profit():
    # 1040 in a protected account + 10 active = total 1050, 50 profit, NOT 1040.
    b=PaperBook(risk=RiskState(month='2027-01',free_cash=Decimal('10'),open_exposure=0,
          protected_cash=Decimal('1040'),phase='PROFIT_ONLY',selections_today=0,
          month_loss_realized=0,week_loss_realized=0,annual_negative_month_loss=0,seen_match_ids=[]))
    n,report=close_month(b,'2027-02')
    assert report.net==Decimal('50') and report.needed_topup==0
    assert n.risk.free_cash==Decimal('1000')


def test_monthly_cap_does_not_enable_more_loss_limit():
    b=book('950')
    n,report=close_month(b,'2027-02')
    assert report.net==Decimal('-50')
    assert n.risk.annual_negative_month_loss==Decimal('50')


def test_forged_select_cannot_bypass_single_bet_cap():
    fake=selection().model_copy(update={'stake':Decimal('100')})
    with pytest.raises(ValueError,match='risk'):
        record_selection(book(),'fixture-forged',fake,Decimal('1.90'),T)


def test_forged_select_cannot_bypass_monthly_floor():
    fake=selection()
    with pytest.raises(ValueError,match='risk'):
        record_selection(book('955'),'fixture-forged',fake,Decimal('1.90'),T)


def test_forged_select_cannot_bypass_daily_cap():
    b=book().model_copy(update={'risk':book().risk.model_copy(update={'selections_today':2})})
    with pytest.raises(ValueError,match='risk'):
        record_selection(b,'fixture-forged',selection(),Decimal('1.90'),T)


def test_forged_select_cannot_bypass_profit_lock():
    with pytest.raises(ValueError,match='risk'):
        record_selection(book('1050'),'fixture-forged',selection(),Decimal('1.90'),T)


def test_forged_select_cannot_bypass_open_exposure_cap():
    initial=record_selection(book(),'fixture-1',selection(),Decimal('1.90'),T)
    second=record_selection(initial,'fixture-2',selection(),Decimal('1.90'),T)
    with pytest.raises(ValueError,match='risk'):
        record_selection(second,'fixture-3',selection(),Decimal('1.90'),T)


def test_forged_select_cannot_spend_locked_principal():
    b=PaperBook(risk=RiskState(month='2027-01',free_cash=Decimal('10'),open_exposure=0,
          protected_cash=Decimal('1040'),phase='PROFIT_ONLY',selections_today=0,
          month_loss_realized=0,week_loss_realized=0,annual_negative_month_loss=0,seen_match_ids=[]))
    with pytest.raises(ValueError,match='risk'):
        record_selection(b,'fixture-forged',selection(),Decimal('1.90'),T)
