# ATP Historical Research Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Historical research adapter + temporal Elo replay + independent XGBoost validation while preserving V0.1's risk gate.

**Architecture:** `research_data` loads and audits tennis-data-style historical CSVs; `research_features` computes pre-match Elo and other historically available features using date-batched updates and the pinned upstream Elo formulas; `research_train` performs separate chronological train/calibrate/test and reports scores vs Elo/market. `__main__` exposes two new commands and never loads a trusted model registry.

**Tech Stack:** Python 3.11+, pandas, NumPy, scikit-learn, XGBoost, optional dependencies; pytest.

**Spec:** `docs/superpowers/specs/2026-11-23-research-pipeline-design.md`

## Global Constraints
- Research only, no live eligible matches, no real-money interfaces.
- Every historical row includes winner/loser *outcome*; feature code cannot use that label until all features for the date are frozen.
- No untimestamped bookmaker odds can enter the V0.1 gate.
- Test full existing suite after each completed subsystem.

## Review Focus
- Winner-first layout spuriously predicting y=1: canonical player order must be independent of result.
- Same-day rematches leaking labels: freeze features before updating any match of that day.
- Odds reversed when canonical order changes: market probabilities match actual player side.
- Calibration overlap with model fitting: split dates into three ordered disjoint blocks.
- Missing match time and player IDs: honest research-only outputs with `live_eligible=false`.

---

### Task 1 — Historical contract and audit
**Files:** Create `src/atp_gate/research_data.py`, `tests/test_research_data.py`.
**Interfaces:** `load_historical_matches(path) -> (list[HistoricalMatch], HistoricalAudit)`.
- [x] Write tests for canonical orientation, ATP tier codes, invalid/duplicate rows, missing odds.
- [x] Run tests expecting missing module failure.
- [x] Implement simple CSV loader and audit counters.
- [x] Rerun focused tests and entire suite.

### Task 2 — Point-in-time Elo/history features
**Files:** Create `src/atp_gate/research_features.py`, `tests/test_research_features.py`.
**Interfaces:** `replay_by_date(matches) -> pandas.DataFrame` with exact V0.1 18-feature names, outcomes and metadata.
- [x] Test pre-day ratings, no future updates before same-day feature capture, complementary outcome labels, correct side-aligned odds.
- [x] Run tests expecting missing module failure.
- [x] Implement day-grouped Elo/form/H2H/rank/count features; do not fill unavailable serve features.
- [x] Rerun focused tests and entire suite.

### Task 3 — Research model validation
**Files:** Create `src/atp_gate/research_train.py`, `tests/test_research_train.py`.
**Interfaces:** `run_research(csv_path, *, min_records, seed) -> dict`.
- [x] Test time-grouped train/calib/test, no market prices used as model features, report fail-closed state, missing/out-of-scope data.
- [x] Run tests expecting missing module failure.
- [x] Implement XGBoost, independent Platt calibration, baseline scores and no-vig odds evaluation.
- [x] Rerun focused tests and entire suite.

### Task 4 — CLI and Windows docs
**Files:** Modify `src/atp_gate/__main__.py`, `pyproject.toml`, `README.md`; add `tests/test_research_cli.py`.
**Interfaces:** `python -m atp_gate research-audit path`, `python -m atp_gate research-train path --out path`.
- [x] Test CLI JSON and invalid input behavior.
- [x] Run tests expecting missing commands failure.
- [x] Implement CLI and optional ML installation instructions.
- [x] Verify whole suite and package with exact path.
