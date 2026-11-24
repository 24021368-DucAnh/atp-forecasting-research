# P1.4d TML–Sackmann Cross-Publication Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deterministic, research-only local audit of 12 historical event match identities across TML and Sackmann-format archive with no automatic player ID join.

**Architecture:** Read-only source SHA/CSV audit + pinned alias registry; aggregate conflict report only.

**Tech Stack:** Python 3.11 stdlib csv/unicodedata/hashlib/pathlib, pytest, four-job Windows/Ubuntu Actions.

**Spec:** `docs/superpowers/specs/2026-11-24-tml-sackmann-crosspublication.md`.

## Hard constraints
- No raw provider data pushed, no official certification, no T−60 odds or profit/stake release.
- No fuzzy matching; only exactly curated aliases and numeric tournament code padding.
- Source rights restricted to personal noncommercial research.
- Build atop existing PR #27 branch; stacked #28/#30 must revalidate after base moves.

### Task 1 — RED tests
**Files:** `tests/test_tml_sackmann_crosscheck.py`, alias registry JSON.
- [ ] Generate deterministic synthetic 340-match twelve-event data where cross-provider match numbers and ID namespaces differ but names/round match, one RET score string differs.
- [ ] Assert 340 matches/339 score exact, review-only flags and no player rows in output; test duplicates/identity swaps/schema changes.
- [ ] Run RED GitHub Actions before production module.

### Task 2 — GREEN audit
**Files:** `src/atp_gate/tml_sackmann_crosscheck.py`.
- [ ] Strict input schema and explicit alias registry/official 12-event crosswalk validation.
- [ ] Build names+event+round uniqueness keys, refuse ambiguous key and report exact match+score counts.
- [ ] Full pytest and 4/4 Actions.

### Task 3 — CLI/documentation and reviews
**Files:** `src/atp_gate/__main__.py`, `docs/TML_NONCOMMERCIAL_RESEARCH.md`, tests.
- [ ] Add CLI `tml-crosspublication-audit` reading local files, writing only aggregate JSON, refusing overwrite input paths.
- [ ] Declare shared-source lineage, name aliases and lack of official independent verification.
- [ ] Full CI/review, update issue #17; stacked PR #28/#30 merge tree regression again.
