# P3A T−60 Quote Receipt Preflight Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide mechanical, fail-closed proof obligations for independent T−60 quote evidence without source access or execution.

**Architecture:** Pure audit of independently timestamped quote/fixture/receipt and external trusted receipt digest. Does not connect to provider nor certify actual offering price.

**Tech Stack:** Python 3.11+ stdlib, Decimal, zone-aware datetime, pytest, 4-job Actions CI.

**Spec:** `docs/superpowers/specs/2026-11-24-p3-quote-receipt-preflight-design.md`

## Global Constraints
- Issue #13 only; do not alter source intake, model training or risk gate and never place any real-money wagers.
- All fields explicit, no timestamp imputation or acceptance of historical opening/closing odds as T−60.
- An exact receipt hash match is evidence of report identity only, not a trust grant; no live eligibility in any output.

## Review Focus
- A later quote timestamp cannot leak into an earlier forecast decision.
- Stale or suspended odds cannot be treated as available.
- Player A/B alignment mismatch must be rejected.
- Actual first serve unknown: cannot certify genuine T−60 relative to actual start.
- Even a perfect synthetic/timestamped record cannot prove market edge or guarantee any profitability.

### Task 1: RED — quotes, timing, source receipt tests
**Files:** `tests/test_quote_receipt.py`.
**Interface:** `audit_quote_receipt(snapshot: dict, *, as_of: datetime, trusted_receipts: Mapping[str,str] | None=None) -> dict`.
- [ ] Create synthetic trusted/untrusted, mismatch, stale, quote future, suspended, unknown rules and scheduling cases.
- [ ] Observe RED in CI before code, then commit tests.

### Task 2: GREEN — strict pure receipt audit
**Files:** `src/atp_gate/quote_receipt.py`.
- [ ] Implement structural validation, source hash check, temporal and market mechanics with explicit reasons.
- [ ] Always output no executable price/no allocation; no provider I/O.
- [ ] Full pytest and 4/4 matrix CI, commit.

### Task 3: Documentation, review, draft PR
**Files:** `docs/P3_T60_RECEIPT_AUDIT.md`.
- [ ] Document as-of contract and independent source provenance responsibility; never assert actual price.
- [ ] Final 4/4 Actions, review and Draft PR; maintain separate P3 source-acquisition blocker.
