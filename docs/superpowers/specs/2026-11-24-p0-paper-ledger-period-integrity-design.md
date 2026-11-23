# P0 — Paper Ledger Period Integrity Design (2026-11-24)

**Status:** Proposed design for review (not yet verified in implementation).  
**Base:** `main` at `1b44f26264d2af06a4424484eff4bec27fe4f57c`.  
**Issue:** [#18](https://github.com/24021368-DucAnh/atp-forecasting-research/issues/18).  
**Safety:** paper-only. No data-source gate, model-eligibility, allocation or real-money integration changes.

## Problem and root cause

Current `RiskState` has a `month` key and two counters named for shorter periods, `selections_today` and `week_loss_realized`, but has **no corresponding day/week key**. `record_selection()` increments the daily count, and `settle_selection()` increments gross weekly losses; `close_month()` is their only explicit reset. The decision gate consumes these counters without validating the period to which they belong. Thus it can carry a "daily" cap across multiple days and erase losses for a week that crosses a month, depending on how an external caller supplies state. These are code-inspected defects; any external period-reset controller is out of scope and is not assumed.

Example: two paper reservations recorded late on Monday, then a fresh Tuesday prediction arrives. Even with no Tuesday reservations, the existing counter remains 2, producing a false `DAILY_LIMIT_REACHED`. Conversely, settling a loss in the final Monday–Sunday week of a month and then calling `close_month` resets the weekly gross-loss cap although the same week continues in the next month.

## Goals

- Make the meaning of daily and weekly counters unambiguous and derived from timestamped, replayable paper journal entries.
- Require explicit Bangkok-local period identity at the `policy.evaluate()` boundary; stale or absent identity must `ABSTAIN` rather than silently trust counters.
- Provide a pure, deterministic period reconciliation path for the caller to prepare a `RiskState` at a known as-of instant.
- Preserve all existing limits (`MAX_STAKE=10`, `MIN_EV=0.02`, 0.25 fractional Kelly, daily count of 2, weekly 30, annual 200, open 20, monthly floor 950, profit-lock rule) **without parameter tuning**.
- Keep untrusted model, missing data, unverified 2024 February source and unverified T−60 evidence fully blocked. No changes to `research_*` or Valuebetennis ingestion.

## Non-goals

- No ledger cryptographic signing, money movement, sportsbook API, claims of real-money enforceability, or model/probability changes.
- No retroactive inference of absent settlement history or invention of financial journal entries.
- No guarantee of profitable performance or optimal Kelly fraction.
- No redefinition of net monthly P&L or `annual_negative_month_loss` in this change.

## Considered approaches

1. **External/manual reset by day/week:** tiny code diff, but reset provenance cannot be audited and `evaluate` may accept stale counters. Rejected.
2. **Pass full journal into every `DecisionInput`:** independent verification at evaluation time, but spreads ledger internals through the existing strict model contract and requires substantial API/test churn. Defer unless pure ledger verification proves insufficient.
3. **Recommended: explicit period keys + journal reconciliation:** add period markers to `RiskState`, reconcile and derive their counters from the paper journal, and ensure `policy.evaluate` rejects missing/stale period markers. It preserves the existing input shape and risk limits while addressing the observed root cause.

The recommendation above is the proposed engineering default, not evidence that the policy is certified or that an external user has approved changed risk semantics.

## Semantics and invariants

1. **Calendar:** all daily/weekly period identities use `Asia/Bangkok`. A day is `YYYY-MM-DD` local. A week is identified by **local Monday date**, thereby crossing calendar months and years safely without relying on `YYYY-WW` ambiguities. UTC-aware `JournalEvent.at` values are converted to Bangkok before bucketing.
2. **Accrual:** each accepted `RESERVE` counts against the local date of `placed_at`. Each `SETTLE_LOSS` counts the originally reserved stake against the local Monday–Sunday week of **settlement**, not reservation. Wins/voids do not raise weekly gross realized losses. `open_exposure` persists until settlement, regardless of day/week.
3. **Journal consistency:** verify chronological event times (nondecreasing; same timestamp allowed), one reserve per match ID, at most one settlement per reserve, no settlement without reserve, settlement not preceding reserve, and value of a loss reconstructed from its original `RESERVE.amount` (because current `SETTLE_LOSS.amount` stores payout 0). Reject future-dated entries relative to chosen `as_of`, invalid/duplicate loss entries, or missing reserve evidence. Do not substitute a guess.
4. **RiskState period identity:** add optional explicit `selection_day` and `loss_week_start` typed as calendar dates for backwards-compatible decoding of old reports. At the policy boundary **missing period fields fail closed**, and mismatched fields relative to `DecisionInput.as_of` add `RISK_PERIOD_UNVERIFIED`; future requests must use new period-aware state.
5. **Reconciliation API:** `reconcile_periods(book: PaperBook, at: datetime) -> PaperBook` replays validated journal, derives exactly the `selections_today` and `week_loss_realized` for `at`, stamps period keys and produces a new immutable-in-usage book. If it sees a *same-period* counter mismatch or a nonempty legacy book with no period identity, raise `ValueError` rather than reset it. Only a newly created empty-journal, zero-counter paper book may be bootstrapped with fresh keys.
6. **Decision and reservation:** `evaluate` must reject an unprepared/stale period state. `record_selection` must ensure the book has been reconciled at `at` **and** does not bypass daily/weekly caps; no implicit success on a caller-supplied zero counter with mismatched journal. It does not claim to certify that a `DecisionOutput` was minted by a trusted model; that remains the existing caller boundary.
7. **Settlement:** `settle_selection` accepts a validated chronological settlement time, derives the period at settlement, increments the correct week's gross loss, and keeps residual exposure correct across day/week transitions. Avoid silently erasing any pending exposure.
8. **Month close:** `close_month` continues to forbid open positions. It must **preserve prior journal history** needed for the Monday–Sunday week spanning months, and derive next period's weekly count from that history rather than resetting it to zero. Logical rollover instant is midnight Bangkok at the first day of `next_month`; reject journal events after that cutoff. Monthly net and `needed_topup` accounting remain unchanged. The full accounting history across month rollover is not cryptographically complete, so do not claim external-proof auditability.
9. **Immutable-use boundary:** avoid sharing a mutable `journal` list across returned `PaperBook` instances. Rebuild rather than mutate events; Pydantic's `frozen` setting alone does not make nested lists/dicts immutable. Full signing/tamper-proof storage is deliberately out of scope.
10. **Reproducibility:** pure functions only; no `datetime.now()` defaults, network access, hidden resets, timezone-naive timestamps or fake transfer events.

## Interfaces and files

- `src/atp_gate/contracts.py`: optional `RiskState.selection_day: date | None`, `RiskState.loss_week_start: date | None`; no changes to `DecisionOutput` or model evidence.
- `src/atp_gate/period_risk.py` (new): pure local-calendar period keys and audited journal replay, scoped to period counters; avoid circular imports by placing reusable primitives here and keeping `PaperBook` integration in `paper_ledger.py`.
- `src/atp_gate/paper_ledger.py`: `reconcile_periods(book, at)`, preflight checks and preserved journal on close.
- `src/atp_gate/policy.py`: minimal fail-closed period-key check before any `SELECT`.
- `tests/test_period_risk.py` (new), `tests/test_gate.py`, `tests/test_ledger.py`: explicit regression and boundary contracts.
- `docs/INPUT_AUDIT.md` or dedicated `docs/PAPER_LEDGER_PERIODS.md`: describe period semantics, caller order and limitations.

## Acceptance scenarios / review focus

- Monday 23:59 → Tuesday 00:00 Bangkok: two prior-day selections no longer count on Tuesday, but still appear in journal; stale Tuesday input cannot be selected.
- Sunday 23:59 → Monday 00:00 and month/year rollover: prior-week losses reset **only on new Monday**, including January 1 when not a Monday; Friday month-end to Saturday same-week losses persist.
- Settlement on another day/week than reservation: loss charged to settlement week; open exposure retained until settlement, then released once.
- Journal missing a reserve, duplicate match ID, repeated or retroactive settlement, inconsistent retained counter, nonmonotonic event time, invalid timezone: fail closed.
- Unrecognized period keys, same-day journal/counter mismatch, stale keys at decision time, old legacy nonzero counters with no dated history: fail closed.
- Monthly `net`, protected principal, external top-up and existing caps are unchanged; no trusted validation registry provided still gives `ABSTAIN`.
- RED→GREEN evidence on new tests, full suite, Windows/Ubuntu Python 3.11/3.12 CI. No data/ or reports/ committed; no changes to model or P1.4d.

## Handoff / human review

Before implementation: review the explicit **settlement-week loss accrual** choice, the opt-in breaking behavior at the policy boundary for legacy period-less risk objects, and the requirement to preserve journal over month close. If changed, update this spec first.

Implementation follows Superpowers `writing-plans` → TDD RED → minimal implementation → GREEN → verification → review → Draft PR. Do not merge to `main` automatically.
