# P1 TML Historical Candidate Audit — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Inspect a locally downloaded TML 2024 CSV for the 12 previously missing February official ATP events while preserving source rights, provenance and no-training gates.

**Architecture:** Read-only streaming CSV audit, explicit official/TML ID crosswalk, deterministic report; expose a CLI wrapper that never overwrites inputs.

**Tech Stack:** Python 3.11+, `csv`, `hashlib`, `collections`, `pathlib`, pytest, four-job GitHub CI.

**Spec:** `docs/superpowers/specs/2026-11-24-p1-tml-feb-audit.md`

## Global Constraints
- Use `PERSONAL_NONCOMMERCIAL_RESEARCH`. Do not redistribute source CSV, invent missing outcomes/times, relabel tier A as Masters, or enable betting/training.
- Keep TML and Valuebetennis as distinct source datasets; retain both SHA/provenance. Never merge on player names.
- Do not change P0 risk, P2 scoring or P3 T−60 modules.

## Review Focus
- A changed 2024 source version must be reported, not assumed identical to GitHub snapshot.
- `tourney_date` is tournament start only; must never be interpreted as individual match time.
- Distinct TML `(tourney_id,match_num)` pairs, valid player IDs and basic match outcome consistency.
- A raw `tourney_level=A` does not override a pinned official ATP250 tier.
- No apparent match/round coverage may promote training, executable odds or commercial use.

### Task 1 — RED: synthetic twelve-event audit test
**Files:** `tests/test_tml_historical_audit.py`.
- [ ] Construct 50-column fixtures for twelve source IDs using crosswalk counts/rounds; assert 340 target rows, 12 event groups, status REVIEW_REQUIRED, safe gates.
- [ ] Add duplicates/unknown event, wrong tiers, invalid rows, schema drift, input overwrite tests.
- [ ] Run pytest RED in Actions before implementing.

### Task 2 — GREEN: audit implementation
**Files:** `src/atp_gate/tml_historical_audit.py`.
- [ ] Strict metadata/crosswalk matching and event-row validations. SHA256 from original file bytes.
- [ ] Report exact events, counts, source snapshot differences and errors with safe outcome. Do not ingest model data.
- [ ] Full suite GREEN, verify Windows/Ubuntu matrix.

### Task 3 — CLI, docs and integration review
**Files:** `src/atp_gate/__main__.py`, `docs/TML_NONCOMMERCIAL_RESEARCH.md`, `tests/test_tml_historical_audit.py`.
- [ ] Support optional report under ignored `reports/`; prevent input overwrite.
- [ ] Explain provider terms, daily updates only from publisher downloads, no raw data committed, source versioning.
- [ ] Verify full CI, open Draft PR and keep source reconciliation issue open for independent official-draw validation.
