# P1.1 Source Quality Profile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Provide a reproducible, read-only, fail-closed quality and coverage profile for one or more historical ATP sources.

**Architecture:** Call the existing `load_historical_matches` to reuse all accepted-row and deduplication rules. Summarize only accepted `HistoricalMatch` records, retain original source-audit and hashes, and expose one CLI without affecting the model or risk gate.

**Tech Stack:** Python 3.11 stdlib, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-11-23-p1-source-quality-design.md`

## Global Constraints
- Preserve existing CLI and scientific report behavior, no historical training changes.
- Historical research only: allocation disabled, trusted validation false, stake zero.
- Never download, redistribute or commit source CSVs or generated reports.
- No assumptions that odds were captured at T−60 or that player names are stable identities.

## Review Focus
1. Duplicate source basenames overwrite provenance even when absolute folders differ — reject before loading.
2. A 2026-only partial file cannot claim 2022–2026 coverage — report missing years and nonzero CLI status.
3. Rejected/retired/duplicate input rows must NOT be counted as accepted observations.
4. Missing bookmaker odds and missing ranks may differ by year — include accepted-row missingness rates.
5. Empty-but-valid source files must not produce green completeness reports.

---

### Task 1 — Read-only profile core
**Files:**
- Create: `src/atp_gate/source_profile.py`
- Create: `tests/test_source_profile.py`

**Interfaces:** `profile_historical_sources(paths, *, expected_start_year=None, expected_end_year=None) -> dict`; consumes `load_historical_matches`.

- [ ] **Step 1:** Write tests for tier/year/source and surface totals, duplicate input files and accepted-only denominators.
- [ ] **Step 2:** Run `pytest tests/test_source_profile.py -q` and verify missing module/function fails.
- [ ] **Step 3:** Implement a narrow profile with invariant aggregate counting and safe status output.
- [ ] **Step 4:** Rerun focused tests; compare totals to source audit.
- [ ] **Step 5:** Commit.

### Task 2 — Explicit expected years and robust fail-closed behavior
**Files:** Same module and tests.
- [ ] **Step 1:** Add tests for missing expected season, no accepted matches, invalid ranges, and missed quotes/ranks.
- [ ] **Step 2:** Verify red on new tests.
- [ ] **Step 3:** Implement inclusive year-coverage validation and warnings.
- [ ] **Step 4:** Verify focused and full suite.
- [ ] **Step 5:** Commit.

### Task 3 — Research profile CLI
**Files:**
- Modify: `src/atp_gate/__main__.py`
- Test: `tests/test_source_profile.py`
- Modify: `README.md`

**Interfaces:** `research-profile [--start-year YYYY --end-year YYYY] PATH...` return 0 for PROFILED, 2 for INCOMPLETE or input error.

- [ ] **Step 1:** Add subprocess test for success and coverage failure exit codes.
- [ ] **Step 2:** Verify expected failure when CLI command is missing.
- [ ] **Step 3:** Add parser and error handling, without touching existing research commands.
- [ ] **Step 4:** Run complete `pytest -q` and CI matrix (Windows + Ubuntu, Python 3.11 + 3.12).
- [ ] **Step 5:** Commit documentation with a one-year and multi-year command, no source download.

### Task 4 — Source rights and provenance record
**Files:**
- Create: `docs/DATA_SOURCE_DECISIONS.md`
- Modify: `docs/THIRD_PARTY_NOTICES.md` only if necessary.

- [ ] **Step 1:** Record Valuebetennis CC BY 4.0 / named source, explicit open/close != T−60, broader Main tour tiers; link to provider statement.
- [ ] **Step 2:** Record Tennis-Data restriction and Sackmann NC/SA, label source license status unverified in code.
- [ ] **Step 3:** Review PR diff and confirm only code/tests/docs are tracked, never raw files.
- [ ] **Step 4:** Ensure all four GitHub Actions jobs pass before marking PR review-ready.

## Acceptance
PR must not be merged until all four test matrix jobs pass, invariant counts and exclusion rules are validated, and unverified source identity/licensing flags remain visible. No model training evidence is introduced.
