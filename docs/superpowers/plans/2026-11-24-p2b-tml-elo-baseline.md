# P2B TML Pre-Tournament Elo Research Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a source-pinned, leakage-aware, pre-tournament Elo baseline across three ATP out-of-time holdout calendar years for private noncommercial research.

**Architecture:** Strict local source loader, frozen-per-event Elo updates delayed 28 days, deterministic per-fold probability scores and event-level uncertainty. No outcome-derived features except past-rated match results and no bookmaker odds.

**Tech Stack:** Python 3.11+, stdlib csv/hashlib/datetime/math/pathlib/random, pytest. GitHub Actions CI Ubuntu/Windows Python 3.11/3.12.

**Spec:** `docs/superpowers/specs/2026-11-24-p2b-tml-elo-baseline.md`.

## Global constraints
- Branch `feat/p2-tml-pre-tournament-elo` stacked on P1 #27/#28 and must not merge before dependencies.
- TML raw source bytes only in owner's private gitignored data directory; synthetic test fixtures only in Git.
- `tourney_date` is tournament start, not individual match time; exact pre-match capability remains unverified.
- No commercial use, sportsbook connections, stake allocation, odds T−60 or model release certification.

## Review focus
- Winner-first rows must not leak the outcome through A/B orientation; use fixed sorted player ID.
- Prior match outcomes from the SAME tournament must not be consumed before any other match of that tournament.
- Cross-year season file `2025.csv` may have a `20241229` tournament; fold under date 2024.
- Missing/duplicate match identifiers, corrupted hash-named file or duplicate source season must reject.
- Published event-level CI uses correlated matches and must be labeled descriptive, not a proven model-edge confidence interval.

### Task 1: RED: source and event temporal contract
**Files:** `tests/test_tml_elo_experiment.py`.
**Interface:** `run_tml_elo_experiment(paths: Sequence[Path], *, test_years=(2023,2024,2025), embargo_days=28, bootstrap_replicates=200, seed=29) -> dict`.
- [ ] Write small multi-season synthetic 50-column fixtures, event pairs with swapped winner ordering, repeated same-event players, cross-year start, retirements, duplicate IDs and hash-qualified file checks.
- [ ] Verify RED in GitHub Actions on missing module before writing production.
- [ ] Commit tests.

### Task 2: GREEN: source-pinned tournament timeline and Elo
**Files:** `src/atp_gate/tml_elo_experiment.py`.
- [ ] Validate local 50-column CSV sources, stream SHA per season, explicit empty/invalid rows; skip ambiguous or non-played results with counts.
- [ ] Group event, freeze prediction state, mature embargoed event batches; no event-local leakage, no winner-first features. Fixed overall and surface Elo.
- [ ] Score same predicted matches for coinflip/overall/surface, 3+ holdout years, event-bootstrap descriptive CIs.
- [ ] Verify full pytest 4/4 CI, commit.

### Task 3: CLI and documentation
**Files:** `src/atp_gate/__main__.py`, `tests/test_tml_elo_experiment.py`, `docs/P2_TML_ELO_RESEARCH.md`.
- [ ] CLI `tml-elo-experiment FILES... --out reports/tml-elo.json` rejects any input overwrite and prints only aggregate stats and SHA evidence.
- [ ] Document owner run steps after `tml-update` for 2021–2025, including explicit status of future information, official draws and absent odds, plus source citation.
- [ ] Full CI, code review and Draft stacked PR; never claim finished project or ROI solely from scores.
