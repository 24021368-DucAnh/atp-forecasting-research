"""Pure paper-only ledger transitions; never connects to any payment or betting API."""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from .contracts import RiskState, DecisionOutput
from .policy import X, apply_profit_lock, MAX_STAKE, MAX_OPEN, MONTHLY_FLOOR, WEEKLY_LOSS_MAX, ANNUAL_NEGATIVE_MONTH_MAX, MIN_STAKE
from .period_risk import BANGKOK, period_keys, replay_journal, PeriodReplay


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
    # The original accepted paper quote belongs to RESERVE only. Optional
    # fields permit replay of legacy LOSS/VOID period counts, never legacy WIN.
    side: Literal["A", "B"] | None = None
    odds: Decimal | None = Field(default=None, gt=Decimal("1"), allow_inf_nan=False)


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
    carried_open_exposure: Decimal = Decimal("0")
    # 'needed_topup' is the deficit needed to begin next month at X;
    # NOT a return, and it must be counted in cash-flow accounting.


def _verify_journal_state(book: PaperBook, replay: PeriodReplay) -> None:
    """Refuse stale/forged counters and records; never silently reset evidence."""
    r = book.risk
    if (r.selection_day is None) != (r.loss_week_start is None):
        raise ValueError("risk period identity is incomplete")
    if r.selection_day is None:
        if (book.journal or book.open_positions or r.open_exposure != 0
                or r.selections_today != 0 or r.week_loss_realized != 0
                or r.seen_match_ids):
            raise ValueError("risk period has unverified legacy activity")
    else:
        if r.loss_week_start != r.selection_day - timedelta(days=r.selection_day.weekday()):
            raise ValueError("risk period day/week identity conflicts")
        if (r.selections_today != replay.daily_counts.get(r.selection_day, 0)
                or r.week_loss_realized != replay.weekly_losses.get(r.loss_week_start, Decimal("0"))):
            raise ValueError("risk period counters disagree with journal")

    if set(book.open_positions) != set(replay.open_stakes):
        raise ValueError("risk journal/open-position identities disagree")
    if r.open_exposure != sum(replay.open_stakes.values(), Decimal("0")):
        raise ValueError("risk open exposure disagrees with journal")
    for match_id, position in book.open_positions.items():
        if (position.match_id != match_id or position.stake != replay.open_stakes[match_id]
                or position.placed_at != replay.reserve_at[match_id]):
            raise ValueError("risk open-position data disagrees with journal")

    this_month_ids = [
        entry.match_id for entry in book.journal
        if entry.event == "RESERVE"
        and entry.at.astimezone(BANGKOK).strftime("%Y-%m") == r.month
    ]
    if len(set(r.seen_match_ids)) != len(r.seen_match_ids) or set(r.seen_match_ids) != set(this_month_ids):
        raise ValueError("risk seen-match IDs disagree with journal")


def reconcile_periods(book: PaperBook, at: datetime) -> PaperBook:
    """Rebuild certified day/week counters from the complete paper journal.

    A caller must pass this derived risk state to `policy.evaluate`. Period
    stamps alone are not an authentication or integrity signature.
    """
    day, week = period_keys(at)
    if book.risk.month != day.strftime("%Y-%m"):
        raise ValueError("risk month mismatch; unsettled cross-month accounting unsupported")
    replay = replay_journal(book.journal, at)
    _verify_journal_state(book, replay)
    if (book.risk.selection_day is not None
            and (book.risk.selection_day > day or book.risk.loss_week_start > week)):
        raise ValueError("risk period is newer than decision timestamp")
    r = book.risk.model_copy(update={
        "selection_day": day, "loss_week_start": week,
        "selections_today": replay.daily_counts.get(day, 0),
        "week_loss_realized": replay.weekly_losses.get(week, Decimal("0")),
    })
    return book.model_copy(update={
        "risk": r, "journal": list(book.journal),
        "open_positions": dict(book.open_positions),
    })


def record_selection(book: PaperBook, match_id: str, decision: DecisionOutput,
                     decimal_odds: Decimal, at: datetime) -> PaperBook:
    """Reserve stake once; caller must pass an evaluated, trusted pre-match decision."""
    if decision.decision != "SELECT" or decision.side is None or decision.stake <= 0:
        raise ValueError("only SELECT decisions may be reserved")
    book = reconcile_periods(book, at)
    if (match_id in book.risk.seen_match_ids or match_id in book.open_positions
            or any(e.event == "RESERVE" and e.match_id == match_id for e in book.journal)):
        raise ValueError("match already selected")
    if (not isinstance(decimal_odds, Decimal)
            or not decimal_odds.is_finite()
            or decimal_odds <= Decimal("1")):
        raise ValueError("invalid nonfinite decimal odds price")
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
                                               amount=stake, at=at,
                                               side=decision.side, odds=decimal_odds)],
    })


def settle_selection(book: PaperBook, match_id: str,
                     outcome: Literal["WIN", "LOSS", "VOID"], at: datetime) -> PaperBook:
    """Settle a reserved selection by explicit settlement outcome, not guessed result.

    An upstream licensed provider must map retirement/walkover rules to outcome.
    """
    if match_id not in book.open_positions:
        raise ValueError("match is not open")
    book = reconcile_periods(book, at)
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
    """Close paper month at stake cost basis, carrying unsettled positions intact.

    No unrealized profit/loss is inferred from future match outcomes or odds.
    Externally funded topups restore the research-equity reference at rollover.
    """
    year,mon=map(int,book.risk.month.split("-"))
    expected_year=year+1 if mon==12 else year
    expected_mon=1 if mon==12 else mon+1
    if next_month != f"{expected_year:04d}-{expected_mon:02d}":
        raise ValueError("next_month must be the next calendar month")
    # The next month begins at local midnight, even when UTC is still
    # the previous day. Preserve journal evidence across the month border.
    boundary = datetime(expected_year, expected_mon, 1, tzinfo=BANGKOK)
    replay = replay_journal(book.journal, boundary - timedelta(microseconds=1))
    _verify_journal_state(book, replay)
    next_day, next_week = period_keys(boundary)
    if replay.daily_counts.get(next_day, 0):
        raise ValueError("new-month reservation found before the month rollover")

    net = book.risk.free_cash + book.risk.protected_cash - X
    report = MonthlyReport(
        month=book.risk.month, net=net,
        protected=book.risk.protected_cash,
        ending_unlocked=book.risk.free_cash,
        needed_topup=max(-net, Decimal("0")),
    )
    year_losses = Decimal("0") if expected_year != year else book.risk.annual_negative_month_loss
    year_losses += max(-net, Decimal("0"))
    newrisk = RiskState(
        month=next_month, free_cash=X, open_exposure=0, protected_cash=0,
        phase="STOPPED" if year_losses >= ANNUAL_NEGATIVE_MONTH_MAX else "NORMAL",
        selection_day=next_day, loss_week_start=next_week,
        selections_today=0,
        month_loss_realized=0,
        week_loss_realized=replay.weekly_losses.get(next_week, Decimal("0")),
        annual_negative_month_loss=year_losses,
        seen_match_ids=[],
    )
    return PaperBook(risk=newrisk, journal=list(book.journal)), report
