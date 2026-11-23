# Cross-Month Paper Position Carry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Support open hypothetical tennis positions across Bangkok-local month/year boundaries without retroactive settlement or P&L misattribution.

**Architecture:** Preserve immutable journal and `PaperPosition` from Issue #18, and carry stake at cost basis through `close_month`. No new event types. Explicitly expose carried principal in `MonthlyReport`.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest. GitHub Actions 4-job Windows/Ubuntu Python 3.11/3.12.

**Spec:** `docs/superpowers/specs/2026-11-24-p0-cross-month-paper-carry-design.md`

## Global Constraints
- Stacked on PR #20 head `8a745dd`; dedicated feature branch `feat/p0-cross-month-carry`; no merging without owner review.
- Retain `MIN_EV=0.02`, 0.25 Kelly, stake/risk caps, `ABSTAIN`, licensing and model restrictions.
- Never backdate a settlement; all period accounting uses `Asia/Bangkok`, no speculative mark-to-market.
- No real-money action or future-market quote assumptions.

## Review Focus
- Open position at month end: include stake **only as a cost-basis asset**, not a realized loss.
- Loss and win settled in the new month: prior-month report unchanged; current-month P&L exactly -stake or +(odds-1)×stake.
- Multiple pending bets: carry correct aggregate O, never double count.
- Year-end open losses: accumulate only in settlement year.
- Corrupted exposure/journal, future event at close, stake exceeding capital, or stale-month settlement: reject.

---

### Task 1 — RED: explicit cross-month financial contracts
**Files:** `tests/test_cross_month_carry.py`, `tests/test_ledger.py`.
**Interfaces:** `close_month(book: PaperBook, next_month: str) -> tuple[PaperBook, MonthlyReport]`, `settle_selection(book, match_id, outcome, at) -> PaperBook`.
- [ ] Add parametric tests for WIN/LOSS/VOID, two pending positions, year/week boundaries and ledger invariants with independently calculated expected values.
- [ ] Run GitHub CI at test-only commit; expected RED from old `close_month` rejecting open positions. Record run ID, error text.
- [ ] Commit tests.

### Task 2 — GREEN: carry pending cost basis with auditable report
**Files:** `src/atp_gate/paper_ledger.py`, `tests/test_ledger.py`.
**Interfaces:** `MonthlyReport.carried_open_exposure: Decimal = 0`; `close_month` preserves `PaperBook.open_positions` and `risk.open_exposure`, sets `risk.free_cash=X - open_exposure`.
- [ ] Implement cost-basis equations from spec with journal preflight via `replay_journal` and `_verify_journal_state`.
- [ ] Replace conflicting legacy test that expected rejection with a test asserting carried stake; preserve unrelated old tests.
- [ ] Run full pytest via GitHub CI to verify GREEN and no regressions; commit.

### Task 3 — Documentation, review and release gate
**Files:** `docs/PAPER_LEDGER_PERIODS.md`, `docs/superpowers/plans/2026-11-24-p0-cross-month-paper-carry.md`.
- [ ] Document prior/current month return attribution, top-up and preserved event timestamps, plus the remaining lack of external journal authentication.
- [ ] Verify 4/4 matrix and no policy/model/source changes. Review diff for zero future information and no double counting.
- [ ] Submit Draft stacked PR referencing #21 and #20; do not merge without owner choice.
