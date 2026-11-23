# P1.2 Provider Identity Inspection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or superpowers:subagent-driven-development to implement this plan task by task. Test-first and reviewable commits.

**Goal:** Provide an independent, honest and identity-aware multi-season Valuebetennis CSV inspection tool before any provider joins or ML training.

**Architecture:** New `valuebetennis_source.py` accepts source local CSVs and returns read-only aggregated quality statistics and safe flags. New CLI subcommand routes to it; no mutation of `HistoricalMatch` or the research policy. Data input never enters a model until a later independently verified tier/main-draw adapter.

**Tech Stack:** Python 3.11+ stdlib csv/hashlib/collections/datetime, pytest and GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-11-23-p1-valuebetennis-inspection.md`

## Global constraints
- No model, position allocation, T−60 or betting API changes.
- CSV files and generated audit outputs stay excluded from Git.
- Provider CC BY 4.0 source attribution included; attribution does not verify each local CSV's origin.
- `Main tour` is NOT translated to ATP250/500; `tour` is a draw-round number.
- Fail closed for duplicate basenames, malformed schema and unsafe identity/winner mismatches.

## Review focus
1. `genre` filtering: WTA must never enter ATP counts, even with valid IDs.
2. `tour` vs circuit confusion: round 0..12 is NOT ATP200/500 taxonomy.
3. A duplicate `match_id` across years must not silently contribute two matches.
4. Partial-year files and missing expected seasons must be labeled incomplete.
5. UTC time without verified first-serve or odds quote timestamps must never pass T−60 validation.

### Task 1 — Read-only source inventory & identity checks
**Files:** Create `tests/test_valuebetennis_source.py`, `src/atp_gate/valuebetennis_source.py`

- [ ] Write pytest fixtures for documented semicolon header and four seasons; assert ATP/WTA exclusion, counts, player IDs, source SHA-256, conditional origin flags, unmatched winner.
- [ ] Run CI test and observe missing module error.
- [ ] Implement strict source schema, input scan and counters; reject unsafe identifiers, preserve raw category without mapping.
- [ ] Observe passing focused tests.

### Task 2 — Temporal, missingness and collision edge cases
**Files:** Same module and tests

- [ ] Write tests for missing year range, missing prices, invalid ISO timestamp, duplicate match ID, alias collisions, invalid round and duplicate basenames.
- [ ] Watch targeted failures, implement smallest adjustments, verify full suite.

### Task 3 — CLI & documentation
**Files:** Modify `src/atp_gate/__main__.py`; create `docs/VALUEBETENNIS_SOURCE_INSPECTION.md`; update README

- [ ] Add subprocess test for `valuebetennis-profile` success and no-data failure exit codes before registering command.
- [ ] Observe CLI red, implement CLI path and error handling; return nonzero for `INCOMPLETE` or malformed input.
- [ ] Describe exact Windows commands and snapshot/license/quote-time limitations.
- [ ] Verify `python -m pytest -q` on all four CI targets.

### Task 4 — Review and PR
- [ ] Review changes against source design, ensure no real data or trade/live code included.
- [ ] Record all 4 green CI checks and resulting test count.
- [ ] Mark draft PR ready for user review, not merge.
- [ ] Track the *unverified real-file schema* and official tournament-tier mapping as blockers in issue #4.

## Acceptance
This PR is code-ready when 4/4 CI pass; **provider ingestion is not yet production accepted** without an actual provider CSV and verified tour-tier/main-draw mapping. Zero stake and historical research only.
