# P1.3a — Tournament Season Inventory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or superpowers:subagent-driven-development to implement this plan task by task. Write failing tests first and run full suite before readiness.

**Goal:** Inventory tournaments by provider ID and UTC season, including round distributions and unresolved metadata, without falsely declaring ATP-tier/main-draw validation.

**Architecture:** Preserve the existing `inspect_valuebetennis_sources` default behavior. Use an opt-in flag to capture tournament-season groups only inside its accepted-row loop; add an independent summary-writing CLI and tested fail-closed rules. Do not add a second parser.

**Tech Stack:** Python 3.11+, stdlib `collections`, `csv`, `datetime`, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-11-23-p1-tournament-inventory.md`

## Global Constraints
- Research/paper only. No real allocations, no trusted T−60, no guessed tier, no model training.
- Source files/reports ignored by Git.
- Group by UTC year + positive tournament ID, not tournament name.
- This inventory does not certify official ATP season, first serve or draw eligibility.
- Preserve all P1.2 default profile numbers/reports.

## Review Focus
1. Same tournament ID reused in multiple years must yield separate rows and totals.
2. Same-year tournament name/category collisions must be flagged, never merged into a guessed official event.
3. Invalid/missing tournament ID/name must be accounted for, with explicit `INCOMPLETE`.
4. WTA/ITF/Challenger, duplicate match ID and invalid rounds must never contribute tournament rows.
5. Missing years or no accepted candidates must produce nonzero CLI result, even when output JSON is saved.

### Task 1 — Tests and tournament grouping
**Files:** create `tests/test_valuebetennis_tournaments.py`; modify `src/atp_gate/valuebetennis_source.py`.
**Interface:** `inspect_valuebetennis_sources(..., include_tournaments=True)` adds `tournament_inventory`.

- [ ] Write synthetic fixture tests for round/year grouping, negative counts, conflicting raw metadata, no inferred tier/main draw.
- [ ] Run red CI; verify missing `include_tournaments` interface is the failure.
- [ ] Implement opt-in aggregator inside accepted-row loop and consistency summary.
- [ ] Run focused tests; review that default report remains unchanged.

### Task 2 — CLI and missing metadata
**Files:** modify `src/atp_gate/__main__.py`; test `tests/test_valuebetennis_tournaments.py`.
**Interface:** `valuebetennis-tournaments --out FILE [--start-year YEAR --end-year YEAR] CSV...`.

- [ ] Add test for valid JSON output, red for missing command, incomplete year exit=2, invalid metadata exit=2.
- [ ] Implement CLI, guarded error exit and no false positive report.
- [ ] Run complete `python -m pytest -q`.

### Task 3 — Documentation and review
**Files:** update `README.md`; add `docs/TOURNAMENT_SEASON_INVENTORY.md`.

- [ ] Add exact PowerShell example with five actual local CSVs, `--out` to ignored reports directory.
- [ ] Record public source row-total cross-check and the 2026 snapshot mismatch between English/French page versions; do not elevate to provider hash verification.
- [ ] Keep a blocker for official per-tournament tier and main draw, and per-round evidence.
- [ ] Verify 4/4 GitHub CI at final head; review changed files and PR; wait for user merge.

## Acceptance
No P1.3 official tier or main-draw mapping is claimed. Only the inspectable inventory is deliverable; official evidence and final model training remain separate tasks.
