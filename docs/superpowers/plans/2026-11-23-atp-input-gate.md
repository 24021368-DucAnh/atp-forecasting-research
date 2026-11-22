# ATP Input Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build strict, tested, fail-closed ATP pre-match evidence gating and paper-only capital accounting around a reusable third-party model.

**Architecture:** Dedicated Pydantic v2 contracts with exact upstream feature schema, pure policy decision function, separate paper ledger and historical CSV audit. Third-party ML is pinned but not bundled or trusted until its as-of adapter and independent validation pass.

**Tech Stack:** Python >=3.11, Pydantic >=2.12, pytest >=8, stdlib csv/decimal/datetime/zoneinfo.

**Spec:** `docs/superpowers/specs/2026-11-23-atp-input-gate-design.md`

## Global Constraints

- NO real bets or payments; `PAPER_ONLY`.
- Normalized event/player IDs and confirmed start time for every live eligible pre-match signal.
- No future quote or training/calibration/test overlap.
- Always `ABSTAIN` on untrusted validation evidence; unknown fields forbidden.
- The minimum EV threshold and staking limits are unvalidated defaults; no claimed ROI.

## Review Focus

- Ambiguous event identity or reversed A/B odds must always abstain.
- Model-produced probabilities may only be evaluated when a separately approved report SHA is allowlisted.
- A historical day-only price must never be represented as an executable T−60 quote.
- Multiple open positions cannot exceed available cash, weekly risk or concurrent exposure cap.
- Month reset must separately record the recapitalization required after losing months.

---

### Task 1: Exact Input Contracts — COMPLETE

**Files:** `src/atp_gate/contracts.py`, `src/atp_gate/feature_schema.py`, `tests/test_gate.py`

- [x] Write failing tests for unknown fields, timezone-naive dates, A/B identity conflict and BO3/BO5 format.
- [x] Verify failing tests.
- [x] Implement Pydantic v2 contracts and ordered 18-feature fingerprint.
- [x] Run tests to verify they pass.

### Task 2: Pre-match Selective Policy — COMPLETE

**Files:** `src/atp_gate/policy.py`, `tests/test_gate.py`

- [x] Write failing tests for stale/future odds, untrusted report hash, missing features, duplicated selections and risk limits.
- [x] Verify failing tests.
- [x] Implement fail-closed input gate, quarter-Kelly candidate stakes, risk-cap restrictions, profit-lock transfer.
- [x] Run tests to verify they pass.

### Task 3: Paper Ledger — COMPLETE

**Files:** `src/atp_gate/paper_ledger.py`, `tests/test_ledger.py`

- [x] Write failing tests for reserve/settle, duplicate, counterfeit SELECT sizing, principal protection and month rollover.
- [x] Verify failing tests.
- [x] Implement pure paper-only accounting and risk guards.
- [x] Run tests to verify they pass.

### Task 4: Historical CSV Quarantine & CLI — COMPLETE

**Files:** `src/atp_gate/historical_audit.py`, `src/atp_gate/__main__.py`, `tests/test_history_audit.py`, `tests/test_cli.py`

- [x] Write failing tests for invalid historic odds, walkovers, wrong format, duplicate, CLI fail-closed behavior.
- [x] Verify failing tests.
- [x] Implement reusable historical data audit, CLI commands and sample inputs.
- [x] Run tests to verify they pass.

### Task 5: Real Source/ML Adapter — NOT STARTED

**Files to create:** `src/atp_gate/adapters/fixture.py`, `src/atp_gate/adapters/odds.py`, `src/atp_gate/adapters/coenensam.py`, `tests/test_source_adapters.py`

- [ ] Establish and document valid source API permissions, rate limits and match/odds timestamp semantics.
- [ ] Write failing tests proving source IDs, as-of joins and 18-feature consistency for historical and live rows.
- [ ] Implement a data adapter for the pinned upstream revision and a real fixture/odds source.
- [ ] Replay and confirm no post-match or post-decision values are used.
- [ ] Re-run full tests and record source/version IDs.

### Task 6: Independent Model & Strategy Validation — NOT STARTED

**Files to create:** `src/atp_gate/evaluation/walkforward.py`, `src/atp_gate/evaluation/strategy.py`, `tests/test_walkforward.py`, `tests/test_budget_parity.py`

- [ ] Define chronologically disjoint train/calibration/validation/test cohorts and complete as-of data history.
- [ ] Build a reproducible market baseline and model calibration on unseen data.
- [ ] Compare top-2/5/10 with matched budget and turnover; compare dynamic stop policies against no-stop under controlled cash accounting.
- [ ] Quantify uncertainty, Brier/log-loss, ROI, max drawdown, capital utilization and sample size.
- [ ] Create a report registry only for independently verified out-of-sample evidence.

### Task 7: Dashboard & Immutable Forecast Logs — NOT STARTED

- [ ] Build app screens for evidence quality, pre-match forecasts, strategic outcomes and no-selection reasons.
- [ ] Add append-only, hash-chained logs and daily/weekly paper-ledger scheduler.
- [ ] Run end-to-end forward paper validation before considering any future rollout.

## Self-review

V0.1 code covers Tasks 1–4; Tasks 5–7 are explicitly unfinished dependencies. There is no live model integration, no independently demonstrated market edge and no financial execution. The default empty report allowlist makes the CLI's demo abstain.
