"""Pure paper-only ledger transitions; never connects to any payment or betting API."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from .contracts import RiskState, DecisionOutput
from .policy import X, apply_profit_lock, MAX_STAKE, MAX_OPEN, MONTHLY_FLOOR, WEEKLY_LOSS_MAX, ANNUAL_NEGATIVE_MONTH_MAX, MIN_STAKE


class PaperPosition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    match_id: str
    side: Literal["A", "B"]
    stake: Decimal = Field(gt=0)
    odds: Decimal = Field(gt=1)
    placed_at: AwareDatetime


class JournalEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    match_id: str
    event: Literal["RESERVE", "SETTLE_WIN", "SETTLE_LOSS", "SETTLE_VOID", "PROFIT_LOCK"]
    amount: Decimal
    at: AwareDatetime


class PaperBook(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    risk: RiskState
    open_positions: dict[str, PaperPosition] = Field(default_factory=dict)
    journal: list[JournalEvent] = Field(default_factory=list)


class MonthlyReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    month: str
    net: Decimal
    protected: Decimal
    ending_unlocked: Decimal
    needed_topup: Decimal
    # 'needed_topup' is the deficit needed to begin next month at X;
    # NOT a return, and it must be counted in cash-flow accounting.


def record_selection(book: PaperBook, match_id: str, decision: DecisionOutput,
                     decimal_odds: Decimal, at: datetime) -> PaperBook:
    """Reserve stake once; caller must pass an evaluated, trusted pre-match decision."""
    if decision.decision != "SELECT" or decision.side is None or decision.stake <= 0:
        raise ValueError("only SELECT decisions may be reserved")
    if match_id in book.risk.seen_match_ids or match_id in book.open_positions:
        raise ValueError("match already selected")
    if decimal_odds <= 1:
        raise ValueError("bad odds")
    # Gate's risk checks should already have run; preserve basic ledger invariants.
    if book.risk.free_cash < decision.stake:
        raise ValueError("insufficient available balance")
    if book.risk.phase == "STOPPED":
        raise ValueError("book is stopped")
    stake = decision.stake
    risk = book.risk
    if (
        at.tzinfo is None
        or stake < MIN_STAKE
        or stake > MAX_STAKE
        or risk.selections_today >= 2
        or risk.open_exposure + stake > MAX_OPEN
        or risk.week_loss_realized + risk.open_exposure + stake > WEEKLY_LOSS_MAX
        or risk.annual_negative_month_loss + risk.open_exposure + stake > ANNUAL_NEGATIVE_MONTH_MAX
        or (risk.phase == "NORMAL" and risk.free_cash >= Decimal("1050"))
        or (risk.phase == "NORMAL" and risk.free_cash - stake < MONTHLY_FLOOR)
        or (risk.phase == "PROFIT_ONLY" and (
            risk.protected_cash < Decimal("1040")
            or stake > risk.free_cash * Decimal("0.20")
        ))
    ):
        raise ValueError("risk constraints violated")
    new_risk = book.risk.model_copy(update={
        "free_cash": book.risk.free_cash - stake,
        "open_exposure": book.risk.open_exposure + stake,
        "selections_today": book.risk.selections_today + 1,
        "seen_match_ids": [*book.risk.seen_match_ids, match_id],
    })
    pos = PaperPosition(match_id=match_id, side=decision.side, stake=stake,
                        odds=decimal_odds, placed_at=at)
    return book.model_copy(update={
        "risk": new_risk,
        "open_positions": {**book.open_positions, match_id: pos},
        "journal": [*book.journal, JournalEvent(match_id=match_id, event="RESERVE",
                                               amount=stake, at=at)],
    })


def settle_selection(book: PaperBook, match_id: str,
                     outcome: Literal["WIN", "LOSS", "VOID"], at: datetime) -> PaperBook:
    """Settle a reserved selection by explicit settlement outcome, not guessed result.

    An upstream licensed provider must map retirement/walkover rules to outcome.
    """
    if match_id not in book.open_positions:
        raise ValueError("match is not open")
    pos = book.open_positions[match_id]
    if at < pos.placed_at:
        raise ValueError("settlement precedes placement")
    payment = (pos.stake * pos.odds) if outcome == "WIN" else (pos.stake if outcome == "VOID" else Decimal("0"))
    loss = pos.stake if outcome == "LOSS" else Decimal("0")
    risk = book.risk.model_copy(update={
        "free_cash": book.risk.free_cash + payment,
        "open_exposure": book.risk.open_exposure - pos.stake,
        "week_loss_realized": book.risk.week_loss_realized + loss,
        "month_loss_realized": book.risk.month_loss_realized + loss,
    })
    transfer = Decimal("0")
    risk, transfer = apply_profit_lock(risk)
    entries = [*book.journal, JournalEvent(match_id=match_id, event="SETTLE_" + outcome,
                                          amount=payment, at=at)]
    if transfer:
        entries.append(JournalEvent(match_id=match_id, event="PROFIT_LOCK",
                                    amount=transfer, at=at))
    open_positions = dict(book.open_positions)
    del open_positions[match_id]
    return book.model_copy(update={"risk":risk, "open_positions":open_positions, "journal":entries})


def close_month(book: PaperBook, next_month: str) -> tuple[PaperBook, MonthlyReport]:
    """Close a settled paper month, record real net and reset to X independently.

    A caller should use an auditable month-close event and prohibit editing it later.
    """
    if book.open_positions or book.risk.open_exposure != 0:
        raise ValueError("open positions must settle before month rollover")
    year,mon=map(int,book.risk.month.split("-"))
    expected_year=year+1 if mon==12 else year
    expected_mon=1 if mon==12 else mon+1
    if next_month != f"{expected_year:04d}-{expected_mon:02d}":
        raise ValueError("next_month must be the next calendar month")
    net = book.risk.free_cash + book.risk.protected_cash - X
    report=MonthlyReport(month=book.risk.month, net=net,
                         protected=book.risk.protected_cash,
                         ending_unlocked=book.risk.free_cash,
                         needed_topup=max(-net,Decimal("0")))
    year_losses=(Decimal("0") if expected_year!=year else book.risk.annual_negative_month_loss)
    year_losses+=max(-net,Decimal("0"))
    newrisk=RiskState(month=next_month,free_cash=X,open_exposure=0,protected_cash=0,
                      phase="STOPPED" if year_losses>=Decimal("200") else "NORMAL",
                      selections_today=0,month_loss_realized=0,week_loss_realized=0,
                      annual_negative_month_loss=year_losses,seen_match_ids=[])
    return PaperBook(risk=newrisk),report
