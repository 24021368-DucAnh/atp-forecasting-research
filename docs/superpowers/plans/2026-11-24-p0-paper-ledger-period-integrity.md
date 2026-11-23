# P0 Paper Ledger Period Integrity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate stale daily/weekly risk counters without inventing history, preserve per-week loss evidence across month close, and refuse selection on an unverified calendar period.

**Architecture:** A pure `period_risk.py` derives Asia/Bangkok day and Monday-start week keys, and replays a timestamped journal to verify reservations and settled losses. `paper_ledger.py` reconciles counters against that replay, while the existing pure `policy.evaluate()` rejects stale/missing markers. Preserve current stake and risk constants; paper-only with no data permissions changes.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest, built-in `datetime`/`zoneinfo`, GitHub CI matrix (Windows/Ubuntu x Python 3.11/3.12).

**Spec:** `docs/superpowers/specs/2026-11-24-p0-paper-ledger-period-integrity-design.md`

## Global Constraints
- `main` base `1b44f26`; implement on isolated existing branch `design/p0-paper-ledger-period-reconciliation`, Draft PR #19; never merge automatically.
- All dates use Asia/Bangkok; keys are date objects. Weeks begin Monday.
- Keep `MIN_EV=0.02`, `0.25` Kelly, `MAX_STAKE=10`, `MAX_OPEN=20`, and all current caps unchanged.
- No new real-money actions, model training, feature changes or historical-source permission assumptions. Incomplete historical data remains ineligible.
- Treat cross-month unsettled settlement as a *separate* issue; do not silently attribute losses to the wrong month.

## Review Focus
- Two reservations before midnight followed by next-day selection: do not leak yesterday's count.
- Late Sunday loss and Monday decision: Monday week resets; Thursday new-month decision in same week **does not** reset gross losses.
- Reserve in one week and settle in next: charge loss to **settlement week**, retain open exposure until settlement.
- Journal with missing reserve, duplicate reservation, second settlement, nonmonotonic/future timestamps or forged journal-counter mismatch: reject; never repair by overwriting evidence.
- Month-close at Bangkok midnight with open positions or already-next-month journal timestamps: reject; preserve gross weekly losses from journal for a week spanning months.

---

### Task 1: Calendar and journal replay foundation
**Files:** Create `src/atp_gate/period_risk.py` and `tests/test_period_risk.py`.

**Interfaces:**
- `period_keys(at: datetime) -> tuple[date, date]` returns local day and Monday start.
- `replay_journal(events: Sequence[JournalEvent], at: datetime) -> PeriodReplay` where `PeriodReplay` fields are `daily_counts: dict[date,int]`, `weekly_losses: dict[date,Decimal]`, `open_stakes: dict[str,Decimal]`, `latest_at: datetime | None`, `all_reserves: set[str]`.
- `JournalEvent` is imported *within* replay or by postponed/type-only reference to avoid cycles; replay reads `event`, `match_id`, `amount`, `at`.

- [ ] Write test of Bangkok midnight, Sunday/Monday and independent expected keys; run pytest (RED missing module).
- [ ] Implement `period_keys`, rerun test (GREEN).
- [ ] Write test reserving Friday and settling Monday with hand-calculated 10-unit weekly loss; include duplicate/settlement-without-reserve/future/out-of-order failures; run (RED).
- [ ] Implement replay with ordered-reserve/settlement state transitions, strict amounts, no guessed history; rerun tests (GREEN).
- [ ] Commit tests and `period_risk.py`.

### Task 2: Period identity contract and policy fail-close
**Files:** Modify `src/atp_gate/contracts.py`, `src/atp_gate/policy.py` and `tests/test_gate.py`.

**Interfaces:**
- `RiskState.selection_day: date | None = None`; `RiskState.loss_week_start: date | None = None` (legacy decoding allowed, decision not allowed until verified).
- `evaluate(DecisionInput)` emits `RISK_PERIOD_UNVERIFIED` for absent/stale markers relative to `as_of`.

- [ ] Add tests: existing valid helper has correct date keys, same input with missing key abstains; mismatched next-day/week key abstains; run (RED).
- [ ] Add optional state markers and gate check referencing `period_keys`; run (GREEN).
- [ ] Ensure untrusted report still refuses every selection; no change in model validation or positive-EV thresholds.
- [ ] Commit.

### Task 3: Ledger reconciliation and transition protection
**Files:** Modify `src/atp_gate/paper_ledger.py`, `tests/test_ledger.py`, extend `tests/test_period_risk.py`.

**Interfaces:**
- `reconcile_periods(book: PaperBook, at: datetime) -> PaperBook` validates old period count against journal replay before switching periods; stamps the target period and derived values.
- `record_selection`, `settle_selection` call reconciliation before updates and never accept a forged or unreconciled same-period counter. Validate all journal reserve IDs against open positions.
- `close_month` preserves historical journal; resets monthly metrics and derives next-week counter for the next-month midnight while disallowing unsettled positions and out-of-period journal events.

- [ ] Add failing tests for two selections Monday and zero Tuesday, week rollover, same-week month rollover, forged counter, duplicate and missing events, and cross-month settlement refusing unsafe accounting.
- [ ] Implement journal reconciliation, consistent reserve/settle processing, explicitly separate open exposure across periods.
- [ ] Restore/update affected legacy tests intentionally (their fixtures may need stamped keys; preserve existing business outcomes).
- [ ] Verify tests and commit.

### Task 4: Reproducibility, documentation, and CI
**Files:** Create `docs/PAPER_LEDGER_PERIODS.md` and update relevant input audit docs only if needed.

- [ ] Document as-of caller flow: reconcile before evaluate, reserve using reconciled book, settle based on licensed outcome, close settled month at Bangkok boundary; include cross-month unsettled positions limitation.
- [ ] Verify policy constants unchanged via source diff, no unrelated files, no data added, no hypothetical profits claimed.
- [ ] Run `python -m pytest -q` on the changed tree in a real Python environment; verify RED→GREEN checkpoints documented.
- [ ] Verify all four GitHub Actions jobs (Ubuntu and Windows 3.11/3.12), inspect failed jobs if any.
- [ ] Request/perform independent code review, fix Critical/Important feedback and reverify. Keep PR draft and obtain user's merge decision.
