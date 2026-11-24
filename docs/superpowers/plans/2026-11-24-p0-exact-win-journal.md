# P0.25a Exact WIN Payout Replay — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve accepted odds in hypothetical paper RESERVE journal events and verify exact corresponding WIN settlement payout.

**Architecture:** Pydantic JournalEvent evidence fields → deterministic replay odds map → cross-check active PaperPosition fields. No external source service and no cash-history certification.

**Tech Stack:** Python 3.11+, Pydantic, Decimal, pytest, Actions Windows/Ubuntu 3.11/3.12.

**Spec:** `docs/superpowers/specs/2026-11-24-p0-exact-win-journal.md`.

## Global Constraints
- Only research/paper ledger; `stake=0` for real execution. Never infer odds from winning returns.
- Existing legacy RESERVE followed by LOSS/VOID may calculate day/week counters only; legacy WIN without reserve odds fails closed.
- No market odds timestamp certification or full cash journal claim.

## Review Focus
- Rewriting WIN amount with reserve odds unchanged must be rejected.
- Tampering position odds must be rejected at reconciliation.
- Missing/nonfinite odds must not bypass exact payout verification.
- Existing settlement-across-month and profit-lock behavior must not regress.
- Legacy manual LOSS/VOID replay must still work for count/loss auditing; no false complete verification.

### Task 1: RED payout & odds provenance tests
**Files:** `tests/test_exact_win_payout_replay.py`.
- [ ] Create minimal paper book with stake 10, odds 1.90, valid time and decision; assert RESERVE carries accepted odds and side.
- [ ] Alter settled WIN `19.00` to `20.00` in an otherwise valid journal; assert `replay_journal` raises `ValueError`.
- [ ] Change `PaperPosition.odds` to `2.00`; `reconcile_periods` must raise.
- [ ] Missing accepted odds on WIN fails, legacy manual LOSS/VOID still counts.
- [ ] Run RED on Actions and confirm failures are from missing functionality.

### Task 2: GREEN minimal implementation
**Files:** `src/atp_gate/paper_ledger.py`, `src/atp_gate/period_risk.py`.
- [ ] Add `side` and `odds` to journal, append both on RESERVE.
- [ ] Check exact Decimal stake × reserved odds on WIN; verify open position odds and side.
- [ ] Defend against nonfinite input and forbids extraneous odds on settlement.
- [ ] Run full pytest and GitHub Actions; verify 4/4.

### Task 3: Documentation and review
**Files:** `docs/PAPER_LEDGER_PERIODS.md` and PR notes.
- [ ] Document new payout-evidence guarantee, legacy limitations and non-certification of full cash/replay integrity.
- [ ] Verify final CI and conduct independent code-review gate before merge into integration.
- [ ] Update Issue #25 with acceptance evidence and 25b cash-accounting milestones.
