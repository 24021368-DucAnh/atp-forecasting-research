# P1.3c Source-backed Tier Registry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Validate explicit, evidence-linked ATP-tier claims against one immutable Valuebetennis tournament JSON snapshot without guessing unreviewed events or authorizing training.

**Architecture:** A standalone pure `audit_tier_registry(inventory:dict, registry:dict, *, inventory_sha256:str)->dict` validates tier assertions against P1.3a events, protects against calendar-year edition splits and reports unresolved coverage. A CLI reads two files, computes SHA-256, and optionally writes a separate ignored JSON audit. All original source/model/risk code is left untouched.

**Tech Stack:** Python 3.11+ stdlib json/datetime/hashlib/pathlib, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-11-23-p1-tier-registry.md`

## Global Constraints
- Model training and live/paper staking must remain disabled from the new source.
- `Main tour` is not an ATP 500 tier; `Masters` is not proof of Masters 1000.
- No broad `tour` code mapping or use of unverified T−60 prices.
- No original input/report overwrites; raw CSV and reports remain Git-ignored.
- Only explicit same-key, same-original-name registry entries may contribute to reviewed-tier counts.
- Valid link syntax is not evidence content verification; URLs must be primary official source pages.

## Review Focus
1. Snapshot hash does not match actual input bytes → fail.
2. Multiple UTC years for same provider ID → prohibit per-year "tier verified" claims pending official edition reconciliation.
3. An invented ID/name or duplicate key → fail, never silently ignore.
4. Known incomplete Australian Open 2024 → recognized tier but still no usable matches.
5. Absent 2024 Rotterdam → report missing expected event, not a fabricated dataset row.
6. Raw category `Masters` for ATP Finals must never become Masters 1000 without explicit vetted official evidence; preferably remain unresolved.

### Task 1 — Tests first
**Files:** create `tests/test_tier_registry.py`.
- [ ] Write a reproducible minimal P1.3a synthetic fixture, include 2024 AO, 2025 Doha and optional cross-year event.
- [ ] Assert exact joined tier counts/history-only vs potential target vs known incomplete, untouched source, and zero model eligibility.
- [ ] Add negative tests: wrong digest, missing source, duplicate keys, invalid evidence host, unreviewed cross-year event, false absent event.
- [ ] Run CI and confirm RED caused by missing `tier_registry` module.

### Task 2 — Minimal pure implementation
**Files:** create `src/atp_gate/tier_registry.py`.
- [ ] Implement only spec-supported validation, deterministic sorted output, conservative status and complete match totals.
- [ ] Verify focused tests, then full existing tests; no changes to `valuebetennis_source.py` or `inventory_review.py`.

### Task 3 — CLI and evidence-backed seed
**Files:** modify `src/atp_gate/__main__.py`; add `docs/registries/valuebetennis_2022_2026_tiers_v1.json`.
- [ ] Add subprocess red tests for CLI successful audit and failsafe invalid report/overwriting original.
- [ ] Implement `valuebetennis-tier-audit INVENTORY REGISTRY [--out PATH]` and JSON status output.
- [ ] Seed a small **checked** set from 2022–26 user's actual inventory for Dallas/Doha/Munich upgrades, 2024 AO & Indian Wells known incomplete; officially documented absent Rotterdam 2024.
- [ ] Re-run matrix; test proves seed matches actual saved snapshot (no training allowed).

### Task 4 — Docs and PR
**Files:** add `docs/TIER_REGISTRY_AUDIT.md`; update `README.md`.
- [ ] Document actual public ATP sources, snapshot hash, human review requirements and scope gates.
- [ ] Review git diff, ensure no raw data/report included.
- [ ] Verify 4 CI jobs Windows/Ubuntu Python 3.11/3.12 and complete test count; update Issue #7; mark PR review-ready without merging.

## Acceptance
The registry is an incremental curated evidence ledger and quality preflight **not an official universal mapping**. It must not say full P1.3 or P2 are complete. All remaining 323-event official mapping and main-draw/coverage gaps stay open.
