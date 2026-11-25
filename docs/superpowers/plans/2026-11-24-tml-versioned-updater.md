# P1.5 Versioned TML Season Updater — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Safely refresh public noncommercial ATP CSV data without overwriting older versions or certifying unfinished research.

**Architecture:** Pure downloadable CSV validation and atomic content-addressed store in `tml_snapshot.py`; fixed provider origin, monotonic daily checks, explicit local CLI.

**Tech Stack:** Python >=3.11, standard library urllib/csv/json/hashlib/pathlib/zoneinfo, pytest, CI Windows/Ubuntu 3.11/3.12.

**Spec:** `docs/superpowers/specs/2026-11-24-tml-versioned-updater.md`.

## Global constraints
- Stacked after PR #27; all raw snapshots live under gitignored `data/` only.
- Personal noncommercial research; respect publisher terms and no raw redistribution.
- No model training authorization, no market/bet execution, no odds inference.

## Review focus
- Same bytes -> unchanged and no duplicated file; changes -> new immutable version, never silent overwrite.
- No daily provider flood; default 24-hour minimum from last successful check.
- HTML response, malformed header/rows, wrong-year, UTF8 decode error, duplicate ID -> fail with no index mutation.
- Unexpected redirect host or source URL not HTTPS -> refuse.
- CI must remain network-free and all four environments pass.

### Task 1 — RED snapshot versioning and safety
**Files:** `tests/test_tml_snapshot.py`.
**Interface:** `update_tml_season(year, root, *, at, fetcher=None, force=False)`.
- [ ] Test first snapshot, unchanged snapshot, changed snapshot, throttle, timestamp, corrupt content, empty header, duplicate IDs, invalid response.
- [ ] Run RED CI and capture missing-module error.

### Task 2 — GREEN updater
**Files:** `src/atp_gate/tml_snapshot.py`.
- [ ] Implement fixed provider URL, 20MiB cap, 50-column parsing, sha256 exact content, atomic version/index writes.
- [ ] Run full pytest and CI; fix any failed test.

### Task 3 — CLI and local scheduler documentation
**Files:** `src/atp_gate/__main__.py`, `tests/test_tml_snapshot.py`, `docs/TML_NONCOMMERCIAL_RESEARCH.md`.
- [ ] Add opt-in `tml-update --year --root [--force]` CLI with safe JSON failure, never fetch during import.
- [ ] Document PowerShell Task Scheduler owner action, default once daily, no training auto-promotion, local files ignored.
- [ ] Full CI 4/4 and review Draft stacked PR.
