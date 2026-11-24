"""P0.25b.1 cash evidence regression tests; synthetic paper units only."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from zoneinfo import ZoneInfo

import pytest

from atp_gate.contracts import DecisionOutput, RiskState
from atp_gate.paper_ledger import PaperBook, record_selection, settle_selection, close_month

TZ = ZoneInfo("Asia/Bangkok")
START = datetime(2027, 1, 1, tzinfo=TZ)
FEB = datetime(2027, 2, 1, tzinfo=TZ)
MAR = datetime(2027, 3, 1, tzinfo=TZ)
END = MAR + timedelta(hours=1)


def opening_book():
    return PaperBook(risk=RiskState(
        month="2027-01", free_cash=D("1000"), open_exposure=0,
        protected_cash=0, phase="NORMAL", selections_today=0,
        month_loss_realized=0, week_loss_realized=0,
        annual_negative_month_loss=0, seen_match_ids=[],
    ))


def fixture():
    from atp_gate.paper_cash_history import OpeningEvidence, close_evidence_from_report
    initial = OpeningEvidence(at=START, amount=D("1000"))
    decision = DecisionOutput(decision="SELECT", side="A", stake=D("10"),
        ev_lower=.05, p_lower=.6, market_probability=.5, reasons=[])
    book = record_selection(opening_book(), "loss", decision, D("1.9"),
                            FEB - timedelta(hours=5))
    book = settle_selection(book, "loss", "LOSS", FEB - timedelta(hours=4))
    book = record_selection(book, "carry", decision, D("1.9"),
                            FEB - timedelta(hours=3))
    book, first = close_month(book, "2027-02")
    book = settle_selection(book, "carry", "WIN", FEB + timedelta(hours=1))
    book, second = close_month(book, "2027-03")
    return book, initial, [close_evidence_from_report(first, FEB),
                            close_evidence_from_report(second, MAR)]


def test_cash_replay_conservation_across_months():
    from atp_gate.paper_cash_history import audit_cash_history
    b, o, c = fixture()
    result = audit_cash_history(b, o, c, END)
    assert result["cash_consistency_verified"] is True
    assert result["free_cash"] == "1000"
    assert D(result["simulated_topups"]) == D("10")
    assert D(result["simulated_withdrawals"]) == D("9")
    assert D(result["net_paper_result"]) == D("-1")
    assert D(result["annual_negative_month_loss"]) == D("10")
    assert result["external_authenticity_verified"] is False
    assert result["allocation_enabled"] is False


@pytest.mark.parametrize("field,value", [
    ("free_cash", D("1001")), ("protected_cash", D("1")),
    ("month_loss_realized", D("1")), ("annual_negative_month_loss", D("0")),
    ("phase", "PROFIT_ONLY"), ("open_exposure", D("1")),
])
def test_cash_replay_detects_forged_snapshot(field, value):
    from atp_gate.paper_cash_history import audit_cash_history
    b, o, c = fixture()
    forged = b.model_copy(update={"risk":b.risk.model_copy(update={field:value})})
    with pytest.raises(ValueError):
        audit_cash_history(forged, o, c, END)


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "topup", "withdrawal", "carry", "future"])
def test_bad_close_evidence_rejected(mutation):
    from atp_gate.paper_cash_history import audit_cash_history
    b, o, c = fixture()
    if mutation == "missing":
        c.pop(0)
    elif mutation == "duplicate":
        c.insert(1, c[0])
    elif mutation == "future":
        c[1] = c[1].model_copy(update={"at":MAR + timedelta(days=1)})
    else:
        field = {"topup":"topup", "withdrawal":"withdrawal", "carry":"carry"}[mutation]
        c[0] = c[0].model_copy(update={field:D("999")})
    with pytest.raises(ValueError):
        audit_cash_history(b,o,c,END)


def test_legacy_missing_reserve_quote_rejected_for_complete_cash_history():
    from atp_gate.paper_cash_history import audit_cash_history
    b,o,c=fixture()
    events=list(b.journal)
    events[0]=events[0].model_copy(update={"odds":None,"side":None})
    with pytest.raises(ValueError):
        audit_cash_history(b.model_copy(update={"journal":events}),o,c,END)


def test_digest_anchor_detects_changed_evidence():
    from atp_gate.paper_cash_history import cash_history_sha256, audit_cash_history
    b,o,c=fixture()
    digest=cash_history_sha256(b,o,c)
    assert len(digest)==64
    assert audit_cash_history(b,o,c,END,expected_sha256=digest)["anchor_matches"] is True
    events=list(b.journal)
    events[0]=events[0].model_copy(update={"side":"B"})
    altered=b.model_copy(update={"journal":events})
    assert cash_history_sha256(altered,o,c)!=digest
    with pytest.raises(ValueError):
        audit_cash_history(altered,o,c,END,expected_sha256=digest)


def test_future_asof_or_missing_opening_rejected():
    from atp_gate.paper_cash_history import audit_cash_history
    b,o,c=fixture()
    with pytest.raises(ValueError):
        audit_cash_history(b,o,c,FEB)
    with pytest.raises(ValueError):
        audit_cash_history(b,o.model_copy(update={"at":FEB}),c,END)


def profit_fixture():
    from atp_gate.paper_cash_history import OpeningEvidence
    b=opening_book()
    decision=DecisionOutput(decision="SELECT",side="A",stake=D("10"),
        ev_lower=.05,p_lower=.6,market_probability=.5,reasons=[])
    for i in range(5):
        at=START+timedelta(days=i+1,hours=1)
        b=record_selection(b,f"w-{i}",decision,D("2.0"),at)
        b=settle_selection(b,f"w-{i}","WIN",at+timedelta(hours=1))
    return b,OpeningEvidence(at=START,amount=D("1000")),START+timedelta(days=5,hours=3)


def test_profit_lock_is_replayed_not_counted_as_external_cash():
    from atp_gate.paper_cash_history import audit_cash_history
    b,o,at=profit_fixture()
    r=audit_cash_history(b,o,[],at)
    assert D(r["free_cash"])==D("10")
    assert D(r["protected_cash"])==D("1040")
    assert D(r["net_paper_result"])==D("50")
    assert D(r["simulated_withdrawals"])==0


def test_missing_profit_lock_rejected_even_if_balances_forged_to_match():
    from atp_gate.paper_cash_history import audit_cash_history
    b,o,at=profit_fixture()
    forged=b.model_copy(update={"journal":b.journal[:-1],
        "risk":b.risk.model_copy(update={"free_cash":D("1050"),"protected_cash":D("0"),"phase":"NORMAL"})})
    with pytest.raises(ValueError):
        audit_cash_history(forged,o,[],at)


def test_early_profit_lock_is_rejected():
    from atp_gate.paper_cash_history import audit_cash_history
    b,o,at=profit_fixture()
    rows=list(b.journal[:2])
    rows.append(b.journal[-1].model_copy(update={"match_id":"w-0","at":rows[-1].at}))
    forged=b.model_copy(update={"journal":rows})
    with pytest.raises(ValueError):
        audit_cash_history(forged,o,[],at)


def test_december_loss_does_not_enter_next_year_budget():
    """Closing December allocates its result to December, not January."""
    b=opening_book()
    b=b.model_copy(update={"risk":b.risk.model_copy(update={"month":"2027-12"})})
    d=DecisionOutput(decision="SELECT",side="A",stake=D("10"),
        ev_lower=.05,p_lower=.6,market_probability=.5,reasons=[])
    at=datetime(2027,12,31,18,tzinfo=TZ)
    b=record_selection(b,"december-loss",d,D("1.9"),at)
    b=settle_selection(b,"december-loss","LOSS",at+timedelta(hours=1))
    jan,report=close_month(b,"2028-01")
    assert report.month=="2027-12"
    assert report.net==D("-10")
    assert report.needed_topup==D("10")
    assert jan.risk.annual_negative_month_loss==D("0")
    assert jan.risk.free_cash==D("1000")


def test_evidence_hash_canonicalizes_decimal_scale_and_timezone():
    from atp_gate.paper_cash_history import cash_history_sha256
    b,o,c=fixture()
    equivalent=o.model_copy(update={"amount":D("1000.000"),
        "at":o.at.astimezone(timezone.utc)})
    assert cash_history_sha256(b,o,c)==cash_history_sha256(b,equivalent,c)


def test_complete_year_history_conserves_december_loss_after_rollover():
    from atp_gate.paper_cash_history import (
        OpeningEvidence, audit_cash_history, close_evidence_from_report,
    )
    b=opening_book()
    opening=OpeningEvidence(at=START,amount=D("1000"))
    closes=[]
    for month in range(2,13):
        boundary=datetime(2027,month,1,tzinfo=TZ)
        b,report=close_month(b,boundary.strftime("%Y-%m"))
        closes.append(close_evidence_from_report(report,boundary))
    d=DecisionOutput(decision="SELECT",side="A",stake=D("10"),
        ev_lower=.05,p_lower=.6,market_probability=.5,reasons=[])
    at=datetime(2027,12,31,18,tzinfo=TZ)
    b=record_selection(b,"synthetic-december",d,D("1.9"),at)
    b=settle_selection(b,"synthetic-december","LOSS",at+timedelta(hours=1))
    boundary=datetime(2028,1,1,tzinfo=TZ)
    b,report=close_month(b,"2028-01")
    closes.append(close_evidence_from_report(report,boundary))
    r=audit_cash_history(b,opening,closes,boundary)
    assert r["closed_months"]==12
    assert D(r["annual_negative_month_loss"])==0
    assert D(r["simulated_topups"])==10
    assert D(r["net_paper_result"])==-10
    assert D(r["free_cash"])==1000
    assert b.risk.week_loss_realized==10


def test_empty_january_opening_is_consistent_without_invented_transactions():
    from atp_gate.paper_cash_history import OpeningEvidence, audit_cash_history
    r=audit_cash_history(opening_book(),OpeningEvidence(at=START,amount=D("1000")),[],START)
    assert r["cash_consistency_verified"] is True
    assert D(r["net_paper_result"])==0
    assert r["match_journal_events"]==0
    assert r["anchor_matches"] is None
