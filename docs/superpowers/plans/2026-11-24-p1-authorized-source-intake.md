# P1.4d Authorized Source Intake Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reject unlicensed, unidentified, tampered or self-certified source corrections before any ATP historical match-level use.

**Architecture:** Local byte-hash verification and strict manifest normalization in `source_intake.py`; CLI wrapper reports review-only outcomes. No data in model training. Independent rights approval is injected as immutable report registry, never inferred from provider HTML.

**Tech Stack:** Python 3.11+, hashlib, pathlib, datetime, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-11-24-p1-authorized-source-intake-design.md`

## Global Constraints
- P1.4d #17 and P1.4 #11 remains blocked until actual match data and rights approved.
- No raw third-party data committed and no normalizing invented 2024 results.
- No live allocation, no trusted model or T−60 claim.
- Daily/weekly paper ledger PR20 and cross-month PR22 are unrelated and not prerequisites to this pure intake layer.

## Review Focus
- A forged `ai_training_allowed=true` is NOT a source license.
- A pre-existing legacy tournament ID row is NOT match-level data or right to scrape.
- Hash matches but official event scope is invalid: reject.
- Source bytes altered after review: reject and report hash mismatch.
- An independent license acceptance alone never establishes actual main draw completeness.

### Task 1 — RED: strict local intake contract
**Files:** Create `tests/test_source_intake.py`.
**Interface:** `audit_source_intake(artifact_path: Path, manifest: dict, *, inventory_sha256: str, allowed_event_keys: set[str], trusted_permission_reports: Mapping[str,str] | None=None) -> dict`.
- [ ] Add synthetic file tests for valid shape but no external trust, trusted rights but still training blocked, all invalid and corrupted input cases.
- [ ] Run failing CI to verify missing interface.
- [ ] Commit test.

### Task 2 — GREEN: authoritative byte and permission checks
**Files:** Create `src/atp_gate/source_intake.py`.
- [ ] Add allowlisted schema and strict path/date/URL/digest checks; explicit legacy archive rejection.
- [ ] Verify file SHA + size from bytes. Treat denied/no independent grant as non-authorized; never enable training or allocations.
- [ ] Run full tests and CI. Commit.

### Task 3 — CLI + docs
**Files:** Modify `src/atp_gate/__main__.py`, `tests/test_source_intake.py`; Create `docs/HISTORICAL_SOURCE_INTAKE.md`.
- [ ] Add `historical-source-intake` CLI that hashes pinned inventory, loads official reference and manifest, rejects --out overwriting any input, prints safe outcome.
- [ ] Add CLI tests for nonexistent source, output into reports dir, no evidence claim, input overwrite.
- [ ] Full 4/4 CI; request review, Draft PR, preserve no external bytes.
