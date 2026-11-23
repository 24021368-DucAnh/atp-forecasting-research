# P1.4a Official Calendar Coverage Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Audit a curated official ATP February 2024 tournament list against the original source tournament JSON without inferring identities or giving any training permission.

**Architecture:** A pure, evidence-pinned `audit_official_calendar_coverage` validates the existing P1.3a inventory, compares independently sourced event dates and city against provisional source candidate groups, and returns a strictly review-required quality report. A CLI optionally writes a separate local JSON. All original modeling and risk policies stay untouched.

**Tech Stack:** Python3.11 stdlib datetime/unicodedata/hashlib/json, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-11-23-p1-official-calendar-coverage.md`

## Global Constraints
- Original source inventory pinned by SHA-256, no raw CSV added to Git.
- Only curated source-backed official calendar rows. Seed: 2024 February, 12 events, 8 ATP250 + 4 ATP500.
- Official city/date match produces **candidate** only, never verified edition or model eligibility.
- Source gap findings never automatically create missing matches or reassign existing source categories.
- Whole-dataset trust flags `tier_mapping_verified=false`, `main_draw_verified=false`, `eligible_for_model_training=0`, `allocation_enabled=false`, `stake=0` remain.
- The official published calendar can differ from actual outcomes; cross-check each seed against ATP results archive.

## Review Focus
1. A new/altered original inventory must be rejected on digest mismatch, not silently relabeled.
2. A February 2024 schedule with no February source group must report all events missing without changing source counts.
3. A source group in a similarly named city but different year/date is **not** accepted.
4. Multiple possible source groups at the same city/time must be marked ambiguous, never merged.
5. Nonofficial evidence host, bad date, duplicate event key, or claims about model allocation fail closed.
6. Successful audit is not dataset completeness; unreviewed months/years remain out-of-scope.

---

### Task 1: Pure comparator (TDD)
**Files:**
- Create `tests/test_official_calendar_coverage.py`.
- Create `src/atp_gate/official_calendar_coverage.py`.

**Interface:** `audit_official_calendar_coverage(inventory:dict, calendar:dict, *, inventory_sha256:str)->dict`.

- [ ] Write minimal fail-first tests with one missing event, one candidate, wrong year and many matches; preserve input dicts.
- [ ] Verify RED specifically missing module/function in GitHub CI.
- [ ] Implement validated join and strict gate flags, use existing `review_tournament_inventory` for source reconciliation.
- [ ] Verify focused tests GREEN and no regression of original P1.3c audit.

### Task 2: Official 2024 reference & command
**Files:**
- Create `docs/registries/atp_2024_february_official_events_v1.json`.
- Modify `src/atp_gate/__main__.py`.
- Extend `tests/test_official_calendar_coverage.py`.

- [ ] Write test asserting seed 12 source-backed events and CLI return 0, plus stale digest / output overwrite return 2.
- [ ] Verify RED against missing seed/CLI.
- [ ] Add curated 2024 official events with archive+calendar sources and exact ATP250/500 categories.
- [ ] Implement CLI file digest, narrow JSON errors and optional local report output.
- [ ] Verify full pytest suite and 4/4 GitHub CI.

### Task 3: Review and documentation
**Files:** `README.md`, `docs/OFFICIAL_CALENDAR_COVERAGE.md`.
- [ ] Document 12 missing official events vs 0 observed February groups and source links.
- [ ] Document exact Windows PowerShell invocation with original pinned JSON and saved full report.
- [ ] Record limitations: candidate-only city/date matching, source snapshot could change, full 2022–2026 mapping not complete.
- [ ] Verify final CI 4/4, review branch files (no raw provider data, no model/policy modifications), and mark PR review-ready for human merge.
