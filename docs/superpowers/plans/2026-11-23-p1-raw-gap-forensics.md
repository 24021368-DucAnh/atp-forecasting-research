# P1.4b Raw Source Gap Forensics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Distinguish missing source CSV rows from records filtered out of the provisional ATP inventory for the confirmed February 2024 official event gaps.

**Architecture:** Add a standalone one-source annual CSV forensic scanner, source-hash anchored to the original P1.3a JSON, with month breakdown and strict candidate-rejection accounting. Reuse the existing P1.4a source+official calendar integrity audit. Add one CLI command with local-only optional saved JSON, keep existing model/risk code unchanged.

**Tech Stack:** Python 3.11+ stdlib csv/hashlib/datetime/pathlib/collections, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-11-23-p1-raw-gap-forensics.md`

## Global Constraints
- Research only. No provider raw files/reports committed.
- Source CSV SHA256 and size must match P1.3a source_files, inventory bytes digest must match official reference.
- Full-file ATP provisional accepted count reconciles to `coverage.by_source`.
- Invalid dates never silently counted as definitely outside month; raw tournament matching is only city suffix + date-window hint.
- Preserve original P1.2 CSV classification semantics. No main draw or training inference. All trust flags zero/false.
- User's real annual CSV lives only on Windows; synthetic CI fixtures do NOT constitute real-file acceptance.

## Review Focus
1. WTA row with matching event city/window must be reported as filtered, never accepted ATP.
2. The requested month includes all circuits, but invalid-date rows cannot be assigned to a month.
3. Duplicate match ID (in one CSV) must not inflate accepted count.
4. Source SHA256 drift or same-name wrong CSV content must reject before printing trustworthy conclusions.
5. A city suffix alias mismatch may under-detect records: report review candidate, not complete/absent proof.

---

### Task 1 — Test the expected forensic behavior
**Files:** Create `tests/test_source_gap_forensics.py`.
- [ ] Write synthetic semicolon source with one accepted Jan ATP match; Feb WTA/Challenger rows in an official city and an invalid-date row, and pinned inventory + official reference.
- [ ] Add tests for accepted/full source counts, explicit February month breakdown, WTA and Challenger filter reasons, per-event diagnostic names/status.
- [ ] Observe RED in GitHub CI: missing forensic module, not malformed fixture.

### Task 2 — Write the minimum pure scanner
**Files:** Create `src/atp_gate/source_gap_forensics.py`.
- [ ] Verify original manifest basename/size/SHA256, validate month and official events/year, call existing P1.4a audit.
- [ ] Scan entire semicolon CSV with same ordered reason hierarchy as existing source adapter, count raw month, rejected valid-date rows, aggregate event city/time candidate counts.
- [ ] Reconcile accepted source count with pinned inventory by-source.
- [ ] Verify focused tests and full suite, document why matched city/time is never a final join.

### Task 3 — CLI, guards and documentation
**Files:** Modify `src/atp_gate/__main__.py`; create `docs/RAW_SOURCE_GAP_FORENSICS.md`; update README.
- [ ] Write tests first for success summary, stale SHA mismatch and output-overwrite failure.
- [ ] Observe RED for absent CLI; implement CLI output and fail-closed status.
- [ ] Run 4/4 CI (Windows/Ubuntu Python 3.11/3.12); review actual logs.
- [ ] Confirm only docs/code/tests changed, no raw source/policy/model changes; PR ready for user review, not merged.

### Task 4 — Real-file acceptance (after human merge)
- [ ] User executes on `data/valuebetennis-matchs-2024.csv` with exact pinned inventory JSON + official February 2024 reference.
- [ ] Examine February raw genre/category/city counts and all 12 official events. Do not promise result before actual execution.
- [ ] If raw event candidates exist, isolate acceptance exclusion vs provider category naming. If zero, classify only as source-city/date nonobservation in this file.
- [ ] Keep P1.4 full completion blocked until independent match/round completeness and official edition identity verified.
