# P2A Matched Fold Score Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correctly score at least three out-of-time ATP forecast folds on exactly the same historical matches without pretending to prove betting profitability.

**Architecture:** Strict input validation, no data joins or model training; compute proper binary scores and cluster bootstrap uncertainty by tournament edition; output never grants market edge or allocation.

**Tech Stack:** Python 3.11+ stdlib, pytest. GitHub Actions Windows/Ubuntu 3.11/3.12.

**Spec:** `docs/superpowers/specs/2026-11-24-p2-matched-fold-score-design.md`

## Global Constraints
- Build on own branch `feat/p2-walkforward-score-audit` from main, Issue #12. No training permission or live allocation.
- Three disjoint chronological fold holds minimum. Zero point-in-time trading claims. Compare same match IDs and outcomes.
- No external data or historic real odds committed.
- No Kelly, risk gate or source pipeline changes.

## Review Focus
- A model missing one market-probability row cannot quietly gain a better score on a smaller sample.
- Same-day training/holdout overlap is forbidden.
- Inconsistent event IDs or duplicate match IDs cannot inflate sample.
- Bootstrapped CI uses event clusters (not treating all match rows as iid).
- A good score on synthetic data cannot be described as a trusted edge or profitable selection.

### Task 1: RED strict fold protocol
**Files:** `tests/test_fold_scoring.py`.
**Interfaces:** `audit_fold_scores(folds: list[dict], *, bootstrap_replicates: int=400, seed: int=20261124) -> dict` in `src/atp_gate/fold_scoring.py`.
- [ ] Write tests for three disjoint folds; deterministic Brier/logloss, output safety and invalid/missing/duplicate/leaky windows.
- [ ] Commit and verify RED missing module in Actions.

### Task 2: GREEN per-fold and aggregate scoring
**Files:** `src/atp_gate/fold_scoring.py`.
- [ ] Strict date and probability validation; compute binary `Brier = mean((p-y)^2)`, `logloss = -mean(y log p + (1-y) log(1-p))` on same rows.
- [ ] Deterministic cluster-resampled intervals for differences of model vs market (resample tournament editions *within each fold*).
- [ ] No trusted artifact or economic ROI metrics; compare identical rows.
- [ ] Commit and verify full pytest.

### Task 3: Document limits, CI and review
**Files:** `docs/P2_MATCHED_FOLD_SCORING.md`.
- [ ] Document input JSON, model score, paired uncertainty and why this is not model training or real betting evidence.
- [ ] Verify no extra data and complete Windows/Ubuntu Python 3.11/3.12 CI; Draft PR, independent review before merge.
