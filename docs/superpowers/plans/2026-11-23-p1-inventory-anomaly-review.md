# P1.3b Tournament Inventory Anomaly Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task by task. Follow test-first RED→GREEN, review evidence and full CI.

**Goal:** Detect cross-year provider IDs, atypical round coverage and special-format tournament pollution in saved P1.3a JSON without guessing official tiers or draw eligibility.

**Architecture:** A standalone pure reader of the saved inventory JSON produces integrity checks and annotated flags. The CLI reads this JSON and prints a compact summary and optionally writes a separate local review report. It does not modify the provider scanner, source CSV, policy, existing research model or saved original report.

**Tech Stack:** Python 3.11+ standard library, pytest, GitHub CI.

**Spec:** `docs/superpowers/specs/2026-11-23-p1-inventory-anomaly-review.md`

## Global Constraints
- No model/market/allocation functionality, no live acceptance.
- Fail closed on inconsistent counts and malformed event key/round counts.
- Name-based special event signals are conservative manual-review flags, not official authorization or exhaustive scope mapping.
- Calendar-year dates are not automatically official tournament edition years.
- All raw or analyzed provider files remain local `data/` and `reports/`.

## Review Focus
1. An ID repeated in December + January must be flagged, not merged.
2. Missing terminal round 12 for a Grand Slam/Masters tournament must be visible.
3. False assumption all `Masters` are Masters 1000 must be blocked by Nitto Finals signal.
4. Reconciliation mismatch between event round counts / accepted overall / by-year must fail.
5. Normal offseason Nov-to-Dec gap must not be flagged as a Jan-Oct event-start gap.

### Task 1 — Pure audit function
**Files:** create `src/atp_gate/inventory_review.py`, `tests/test_inventory_review.py`

- [ ] Create synthetic inventory JSON tests proving detected cross-year IDs, missing final code 12, special-event flags, gaps, and no automatic tier mapping.
- [ ] Observe CI RED: missing `inventory_review` module.
- [ ] Implement minimal pure function returning deterministic, source-grounded review.
- [ ] Re-run focused suite and check old P1.3a defaults unchanged.

### Task 2 — Defensive validation and CLI
**Files:** `src/atp_gate/inventory_review.py`, `src/atp_gate/__main__.py`, `tests/test_inventory_review.py`

- [ ] Test invalid original totals/by-year/round counts, duplicate event key, and missing input file -> no false success.
- [ ] Observe RED.
- [ ] Implement validation and `valuebetennis-review INPUT [--out OUTPUT]` command; no writes without --out.
- [ ] Test both valid CLI JSON and invalid CLI exit code 2.

### Task 3 — Docs and review
**Files:** `README.md`, `docs/INVENTORY_ANOMALY_REVIEW.md`

- [ ] Document 2024 AO and Indian Wells anomalies with independent primary-source URLs and observed file IDs.
- [ ] Document source JSON checksum and explicit data availability limitations.
- [ ] Run complete CI 4/4 and review GitHub diff; no raw CSV/report or changes to modeling/risk.
- [ ] Open PR for user review, no automatic merge.

## Acceptance
Code may pass CI; **dataset remains blocked** until authoritative per-event tier/year mapping, documented main draw and proper coverage/odds validation exist. Output always `REVIEW_REQUIRED`, `eligible_for_model_training=0`, `allocation_enabled=false`, `stake=0`.
