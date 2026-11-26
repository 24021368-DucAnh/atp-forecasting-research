"""Versioned, read-only verification of synthetic paper cash history.

This verifies arithmetic and evidence consistency, not external authenticity.
It does not place wagers, fund accounts, authorize allocation, or certify profit.
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from decimal import Decimal, DecimalException
import hashlib
import hmac
import json
import re
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from .contracts import RiskState
from .paper_ledger import JournalEvent, MonthlyReport, PaperBook, PaperPosition
from .period_risk import BANGKOK, period_keys, replay_journal

D = Decimal
ZERO = D("0")
OPENING = D("1000")
LOCK_TRIGGER = D("1050")
LOCK_AMOUNT = D("1040")
ANNUAL_LIMIT = D("200")
SCHEMA = "PAPER_CASH_HISTORY_V1"


class OpeningEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    at: AwareDatetime
    amount: Decimal = Field(gt=0, allow_inf_nan=False)


class MonthCloseEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    at: AwareDatetime
    month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    net: Decimal = Field(allow_inf_nan=False)
    topup: Decimal = Field(ge=0, allow_inf_nan=False)
    withdrawal: Decimal = Field(ge=0, allow_inf_nan=False)
    carry: Decimal = Field(ge=0, allow_inf_nan=False)
    protected: Decimal = Field(ge=0, allow_inf_nan=False)
    ending_unlocked: Decimal = Field(ge=0, allow_inf_nan=False)


def close_evidence_from_report(report: MonthlyReport, boundary: datetime) -> MonthCloseEvidence:
    """Capture an explicit hypothetical close record; audit independently verifies it."""
    return MonthCloseEvidence(
        at=boundary, month=report.month, net=report.net,
        topup=report.needed_topup, withdrawal=max(report.net, ZERO),
        carry=report.carried_open_exposure, protected=report.protected,
        ending_unlocked=report.ending_unlocked,
    )


def _decimal_token(value: Decimal) -> str:
    """Canonical exact decimal tuple; does not round via ambient Decimal context."""
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValueError("nonfinite or invalid paper cash decimal")
    sign, digits, exponent = value.as_tuple()
    if not any(digits):
        return "0"
    while digits[-1] == 0:
        digits = digits[:-1]
        exponent += 1
    return ("-" if sign else "") + "".join(map(str, digits)) + "e" + str(exponent)


def _canonical(value):
    if isinstance(value, Decimal):
        return _decimal_token(value)
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("paper cash evidence requires aware timestamps")
        return value.astimezone(timezone.utc).isoformat(timespec="microseconds")
    if isinstance(value, BaseModel):
        return _canonical(value.model_dump(mode="python"))
    if isinstance(value, dict):
        return {k: _canonical(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonical(v) for v in value]
    return value


def cash_history_sha256(
    book: PaperBook, opening: OpeningEvidence, closes: Sequence[MonthCloseEvidence],
) -> str:
    """Hash evidence only, not mutable end-state balances or an asserted as-of time."""
    evidence = {"schema": SCHEMA, "opening": opening, "journal": book.journal,
                "closes": list(closes)}
    payload = json.dumps(_canonical(evidence), sort_keys=True, ensure_ascii=False,
                         allow_nan=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _next_boundary(at: datetime) -> datetime:
    local = at.astimezone(BANGKOK)
    return datetime(local.year + int(local.month == 12),
                    1 if local.month == 12 else local.month + 1, 1, tzinfo=BANGKOK)


def _month(at: datetime) -> str:
    return at.astimezone(BANGKOK).strftime("%Y-%m")


def audit_cash_history(
    book: PaperBook, opening: OpeningEvidence, closes: Sequence[MonthCloseEvidence],
    as_of: datetime, *, expected_sha256: str | None = None,
) -> dict:
    """Replay complete cash evidence and reconcile the supplied paper snapshot.

    A digest match is not authentication: the expected digest must be separately
    trusted by the caller. No missing legacy cash or price evidence is invented.
    """
    try:
        return _audit(book, opening, closes, as_of, expected_sha256)
    except DecimalException as exc:
        raise ValueError("invalid paper cash arithmetic") from exc


def _audit(book, opening, closes, as_of, expected_sha256):
    day, week = period_keys(as_of)
    # Revalidate copies, because model_copy(update=...) bypasses field checks.
    opening = OpeningEvidence.model_validate(opening.model_dump())
    closes = [MonthCloseEvidence.model_validate(c.model_dump()) for c in closes]
    journal = [JournalEvent.model_validate(e.model_dump()) for e in book.journal]
    risk = RiskState.model_validate(book.risk.model_dump())
    positions = {k: PaperPosition.model_validate(v.model_dump())
                 for k, v in book.open_positions.items()}
    normalized = PaperBook(risk=risk, journal=journal, open_positions=positions)
    start = opening.at.astimezone(BANGKOK)
    if start != datetime(start.year, 1, 1, tzinfo=BANGKOK) or opening.amount != OPENING:
        raise ValueError("cash history requires January 1 opening at reference balance")
    if opening.at > as_of:
        raise ValueError("opening is after as-of time")
    if risk.month != _month(as_of):
        raise ValueError("cash snapshot month does not match as-of month")

    digest = cash_history_sha256(normalized, opening, closes)
    if expected_sha256 is not None:
        if not isinstance(expected_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None:
            raise ValueError("invalid expected cash history digest")
        if not hmac.compare_digest(digest, expected_sha256):
            raise ValueError("cash history digest differs from supplied anchor")

    replay = replay_journal(journal, as_of)
    # Month-close evidence must cover every elapsed boundary exactly once.
    next_boundary = _next_boundary(start)
    for close in closes:
        if close.at != next_boundary or close.at > as_of:
            raise ValueError("missing, duplicate, future, or misdated month close")
        next_boundary = _next_boundary(next_boundary)
    if next_boundary <= as_of:
        raise ValueError("missing elapsed month-close evidence")

    if any(e.at < opening.at for e in journal):
        raise ValueError("match journal precedes opening")
    if any(e.event == "RESERVE" and (e.odds is None or e.side is None) for e in journal):
        raise ValueError("complete cash audit requires accepted reserve price and side")

    free, protected = OPENING, ZERO
    topups = withdrawals = annual_losses = month_losses = ZERO
    month = _month(start)
    phase: Literal["NORMAL", "PROFIT_ONLY", "STOPPED"] = "NORMAL"
    seen = []
    open_positions = {}
    pending_lock = None

    # Stable chronology, with explicit close before any match event at midnight.
    stream = [(c.at, 0, c) for c in closes]
    stream.extend((e.at, 1, e) for e in journal)
    stream.sort(key=lambda item: (item[0], item[1]))

    for at, kind, event in stream:
        if pending_lock is not None and not (
            kind == 1 and event.event == "PROFIT_LOCK"
            and (event.match_id, event.at) == pending_lock
        ):
            raise ValueError("required profit lock is missing")
        if kind == 0:
            carry = sum((p.stake for p in open_positions.values()), ZERO)
            net = free + protected + carry - OPENING
            topup, withdrawal = max(-net, ZERO), max(net, ZERO)
            if (event.month != month or event.net != net or event.carry != carry
                    or event.topup != topup or event.withdrawal != withdrawal
                    or event.protected != protected or event.ending_unlocked != free):
                raise ValueError("month-close cash evidence disagrees with independent replay")
            if carry > OPENING:
                raise ValueError("carried paper cost basis exceeds opening reference")
            topups += topup
            withdrawals += withdrawal
            new_month = _month(at)
            # A December loss belongs to the closed year, not the new one.
            annual_losses = (annual_losses + max(-net, ZERO)
                             if new_month[:4] == month[:4] else ZERO)
            free, protected = OPENING - carry, ZERO
            month_losses = ZERO
            phase = "STOPPED" if annual_losses >= ANNUAL_LIMIT else "NORMAL"
            month, seen = new_month, []
            continue

        if _month(at) != month:
            raise ValueError("match event lacks its month-close evidence")
        if event.event == "RESERVE":
            if phase == "STOPPED" or free < event.amount:
                raise ValueError("reserve violates paper cash availability")
            free -= event.amount
            open_positions[event.match_id] = PaperPosition(
                match_id=event.match_id, side=event.side, odds=event.odds,
                stake=event.amount, placed_at=event.at)
            seen.append(event.match_id)
        elif event.event in ("SETTLE_WIN", "SETTLE_LOSS", "SETTLE_VOID"):
            pos = open_positions.pop(event.match_id)
            # replay_journal has already independently verified exact payout.
            free += event.amount
            if event.event == "SETTLE_LOSS":
                month_losses += pos.stake
            if phase == "NORMAL" and not open_positions and free >= LOCK_TRIGGER:
                pending_lock = (event.match_id, event.at)
        elif event.event == "PROFIT_LOCK":
            if pending_lock != (event.match_id, event.at) or event.amount != LOCK_AMOUNT:
                raise ValueError("unexpected profit lock")
            free -= event.amount
            protected += event.amount
            phase = "PROFIT_ONLY"
            pending_lock = None

    if pending_lock is not None:
        raise ValueError("required profit lock missing at end of journal")
    exposure = sum((p.stake for p in open_positions.values()), ZERO)
    if (risk.free_cash != free or risk.protected_cash != protected
            or risk.open_exposure != exposure or risk.month_loss_realized != month_losses
            or risk.annual_negative_month_loss != annual_losses or risk.phase != phase
            or risk.month != month or risk.seen_match_ids != seen
            or positions != open_positions):
        raise ValueError("paper snapshot cash or positions disagree with independent replay")

    # The stored counters describe the last reconciled local day, not necessarily
    # today's as-of day; require a valid day/week within observed history.
    if risk.selection_day is None or risk.loss_week_start is None:
        if (risk.selection_day is not None or risk.loss_week_start is not None
                or journal or closes or risk.selections_today or risk.week_loss_realized):
            raise ValueError("paper snapshot lacks complete period counters")
    else:
        last_day = max([start.date()] + [period_keys(e.at)[0] for e in journal]
                       + [period_keys(c.at)[0] for c in closes])
        stored_day = risk.selection_day
        stored_week = stored_day - timedelta(days=stored_day.weekday())
        if (not last_day <= stored_day <= day or stored_day.strftime("%Y-%m") != month
                or risk.loss_week_start != stored_week
                or risk.selections_today != replay.daily_counts.get(stored_day, 0)
                or risk.week_loss_realized != replay.weekly_losses.get(stored_week, ZERO)):
            raise ValueError("paper snapshot period counters disagree with cash evidence")

    # Conservation includes open stakes at cost, not marked-to-market gains.
    net_result = free + protected + exposure + withdrawals - topups - opening.amount
    return {
        "status": "PAPER_CASH_CONSISTENCY_VERIFIED",
        "schema": SCHEMA,
        "cash_consistency_verified": True,
        "policy_compliance_verified": False,
        "evidence_sha256": digest,
        "anchor_matches": True if expected_sha256 is not None else None,
        "external_authenticity_verified": False,
        "free_cash": str(free), "protected_cash": str(protected),
        "open_exposure": str(exposure), "month_loss_realized": str(month_losses),
        "annual_negative_month_loss": str(annual_losses),
        "simulated_topups": str(topups), "simulated_withdrawals": str(withdrawals),
        "net_paper_result": str(net_result), "closed_months": len(closes),
        "match_journal_events": len(journal), "allocation_enabled": False,
        "stake": 0,
    }
