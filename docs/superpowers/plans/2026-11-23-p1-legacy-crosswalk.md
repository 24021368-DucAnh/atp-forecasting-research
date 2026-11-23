# P1.4c Legacy Archive Crosswalk Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strictly cross-reference the 12 Valuebetennis legacy tournament IDs for February 2024 to a pinned official ATP event calendar while preventing accidental match imports or claims that old HTML is CC BY 4.0.

**Architecture:** Add a pure JSON-to-JSON audit function calling P1.4a source integrity, a manually checked metadata-only 12-row manifest, and a read-only CLI that optionally writes a separate ignored local report. No programmatic scrape or external match data ingestion.

**Tech Stack:** Python 3.11+ stdlib, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-11-23-p1-legacy-crosswalk.md`

## Global constraints
- Legacy listing pages do not confer match-level rights, identity or results.
- Snapshot pin `eccb403bb6c0874e30f4e304c7be23678d2d1e6db095fd9174ee1753a225665b` mandatory.
- Event keys must be exact 12/12 official calendar keys; names/city/date/sex and provider IDs validated.
- All model training / main-draw / timestamped odds / allocation safety flags false or zero.
- Git only receives curated small metadata, code, tests, docs; no raw third-party datasets.

## Review focus
1. Legacy provider ID appears in 2024 source inventory -> never falsely label absent (error).
2. WTA / Challenger listed instead of an ATP main-tour metadata row -> error.
3. Incorrect city/date or duplicate legacy ID / event key -> error, not fuzzy guess.
4. Source snapshot SHA mismatch -> error, even if names look correct.
5. Missing exact 2024 Feb event manifest row -> fail, never report full 12 coverage.
6. CSV CC BY licence status must not be reused as legacy HTML rights grant.
7. CLI --out path identical to any input -> error with no overwrite.

### Task 1 — TDD pure crosswalk
**Files:** create `tests/test_legacy_crosswalk.py`, `src/atp_gate/legacy_archive_crosswalk.py`.

- [ ] Write synthetic original-inventory/official-calendar/legacy-manifest fixtures with one Rotterdam entry.
- [ ] Assert safe unverified review, provider-ID absence, official key match; check result flags remain zero/false and inputs unchanged.
- [ ] Add explicit negative tests from review focus, observe RED in CI for missing module.
- [ ] Implement pure function; verify focused tests GREEN without modifying old source adapters.

### Task 2 — Real curated metadata and CLI
**Files:** create `docs/registries/valuebetennis_legacy_2024_02_crosswalk_v1.json`, modify `src/atp_gate/__main__.py`, extend tests.

- [ ] Write test that curated manifest has exact 12 event keys/IDs, exact source snapshot and rights warning; write subprocess CLI test.
- [ ] Confirm missing seed/CLI tests RED in CI.
- [ ] Add 12 **metadata only** rows transcribed from public historical archive; note provider archive index is not licensed match data.
- [ ] Implement `valuebetennis-legacy-crosswalk INVENTORY CALENDAR LEGACY [--out FILE]`, with SHA from inventory bytes, no overwrite and JSON summaries on success/errors.
- [ ] Run full pytest suite and verify all four GitHub CI combinations.

### Task 3 — Documentation and review
**Files:** create `docs/LEGACY_ARCHIVE_CROSSWALK.md`, update README.
- [ ] Link authoritative ATP / provider export terms and legacy index.
- [ ] Describe correct use: evidence crosswalk, not authorized backfill or automatic match scraping.
- [ ] Provide exact Windows command; note real-source invocation pending after merge.
- [ ] Review PR file list and Green CI, update Issue #11, ready for human review (do not auto merge).

## Acceptance
P1.4c metadata and rights **preflight** is complete only after real-source user run. Dataset match completeness, official main draw, and season-wide P1.4 are separate, unsatisfied gates. Source licenses require human/provider review for HTML-derived match content.
