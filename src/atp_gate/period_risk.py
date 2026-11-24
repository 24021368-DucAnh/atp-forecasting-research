"""Deterministic Asia/Bangkok period keys and paper-journal integrity replay.

The caller must independently authenticate its journal; this module checks the
internal evidence, not the provenance or commercial validity of any wagers.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from collections.abc import Sequence
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from .paper_ledger import JournalEvent

BANGKOK = ZoneInfo("Asia/Bangkok")


def period_keys(at: datetime) -> tuple[date, date]:
    """Return Bangkok-local calendar day and the Monday starting its week."""
    if at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("risk journal timestamps must be timezone-aware")
    day = at.astimezone(BANGKOK).date()
    return day, day - timedelta(days=day.weekday())


@dataclass(frozen=True)
class PeriodReplay:
    daily_counts: dict[date, int]
    weekly_losses: dict[date, Decimal]
    open_stakes: dict[str, Decimal]
    latest_at: datetime | None
    all_reserves: set[str]
    reserve_at: dict[str, datetime]
    reserve_odds: dict[str, Decimal]
    reserve_sides: dict[str, str]


def replay_journal(events: Sequence[JournalEvent], at: datetime) -> PeriodReplay:
    """Replay reserve/settlement history, refusing nonmonotone or forged events.

    A loss journal event stores payout zero; its gross-loss amount comes from
    the corresponding reserve. It cannot be reconstructed without that reserve.
    """
    period_keys(at)  # reject naive clock before reading events
    counts: dict[date, int] = {}
    losses: dict[date, Decimal] = {}
    open_stakes: dict[str, Decimal] = {}
    reserve_at: dict[str, datetime] = {}
    reserve_odds: dict[str, Decimal] = {}
    reserve_sides: dict[str, str] = {}
    all_reserves: set[str] = set()
    settled: set[str] = set()
    latest: datetime | None = None
    last_settlement: tuple[str, datetime] | None = None
    profit_locked: set[tuple[int, int]] = set()

    for entry in events:
        day, week = period_keys(entry.at)
        # model_copy(update=...) bypasses Pydantic field validation, so replay
        # must validate original and potentially mutated journal values too.
        if not isinstance(entry.amount, Decimal) or not entry.amount.is_finite():
            raise ValueError("nonfinite paper journal amount")
        if entry.odds is not None and (
            not isinstance(entry.odds, Decimal)
            or not entry.odds.is_finite() or entry.odds <= Decimal("1")
        ):
            raise ValueError("invalid nonfinite accepted odds price")
        if entry.event != "RESERVE" and (
            entry.odds is not None or entry.side is not None
        ):
            raise ValueError("settlement or profit-lock cannot change accepted odds/side")
        if entry.at > at:
            raise ValueError("future paper journal event")
        if latest is not None and entry.at < latest:
            raise ValueError("paper journal events are not chronological")
        latest = entry.at

        if entry.event == "RESERVE":
            # A complete new accepted quote needs both price and selected
            # side. Legacy reserve rows may contain neither, but can only
            # replay LOSS/VOID period counts, never certify WIN payouts.
            if entry.side not in (None, "A", "B"):
                raise ValueError("invalid reserve accepted side")
            if (entry.side is None) != (entry.odds is None):
                raise ValueError("partial reserve quote: accepted side and odds required together")
            if entry.match_id in all_reserves or entry.amount <= 0:
                raise ValueError("duplicate or invalid paper reserve")
            all_reserves.add(entry.match_id)
            open_stakes[entry.match_id] = entry.amount
            reserve_at[entry.match_id] = entry.at
            if entry.odds is not None:
                reserve_odds[entry.match_id] = entry.odds
            if entry.side is not None:
                reserve_sides[entry.match_id] = entry.side
            counts[day] = counts.get(day, 0) + 1
            last_settlement = None
        elif entry.event in ("SETTLE_WIN", "SETTLE_LOSS", "SETTLE_VOID"):
            if entry.match_id not in open_stakes:
                raise ValueError("paper settlement without a unique open reserve")
            reserved = open_stakes.pop(entry.match_id)
            if entry.event == "SETTLE_LOSS":
                if entry.amount != 0:
                    raise ValueError("loss journal payout must be zero")
                losses[week] = losses.get(week, Decimal("0")) + reserved
            elif entry.event == "SETTLE_VOID":
                if entry.amount != reserved:
                    raise ValueError("void journal must refund original stake")
            else:
                accepted_odds = reserve_odds.get(entry.match_id)
                if accepted_odds is None:
                    raise ValueError("win payout unverified: reserve has no accepted odds")
                if entry.amount != reserved * accepted_odds:
                    raise ValueError("win payout must equal original stake times accepted odds")
            settled.add(entry.match_id)
            last_settlement = (entry.match_id, entry.at)
        elif entry.event == "PROFIT_LOCK":
            month_key = (day.year, day.month)
            if (last_settlement != (entry.match_id, entry.at)
                    or entry.amount != Decimal("1040")
                    or month_key in profit_locked):
                raise ValueError("unverified or repeated paper profit lock")
            profit_locked.add(month_key)
            last_settlement = None
        else:
            raise ValueError("unrecognized paper journal event")

    return PeriodReplay(daily_counts=counts, weekly_losses=losses,
                        open_stakes=open_stakes, latest_at=latest,
                        all_reserves=all_reserves, reserve_at=reserve_at,
                        reserve_odds=reserve_odds, reserve_sides=reserve_sides)
