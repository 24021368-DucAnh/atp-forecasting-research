# V4.0 S1 historical evidence read model Implementation Plan

> **For agentic workers:** use superpowers:executing-plans and test-driven-development. Stop after actual RED until verified, then minimal GREEN. Independent review before exact-head owner merge.

**Goal:** expose verified historical evidence to an offline read-only dashboard without network, fitting, DB or Streamlit dependencies.
**Architecture:** separate atp_lab package from frozen atp_gate. One pure reader, then UI in a separate bounded step. Source is committed P2.4 aggregate evidence, not raw records.
**Spec:** docs/superpowers/specs/2026-11-26-v4-local-dashboard-design.md
**Tech stack:** Python 3.11+, stdlib; pytest. Streamlit for subsequent UI only.
**Constraints:** base 410ec717a69c58e5724a93e364158219c1447f1e; no changes to V3 evidence/permissions or CI settings; real-data ingestion and training locked; no new data. Canonical manifest updated atomically for new files.

## Task 1: historical view contract
Files: tests/v4/test_historical.py; src/atp_lab/__init__.py; src/atp_lab/historical.py.
Interface: read_historical_evidence(path: Path) -> dict, exact SHA256 check, raises ValueError for unreadable/mismatched data. Returns scope, n, models keyed by candidate name, folds (year, n), flags (real_data_active false, model_validation_trusted false); each model contains accuracy, correct, n, log_loss, brier, ece, coverage. Bin 0-4 chooses B; bin 5-9 chooses A, tie A. Require 18 matched models; never treat this as prospective results. No source fetch or mutating file.
- [ ] RED test valid archived evidence, metric fidelity, 18 candidates, support and fail-closed tamper/missing path; run pytest tests/v4/test_historical.py -q; expected failure from absent atp_lab reader.
- [ ] GREEN implement reader using stdlib, verify exact hash before decode, validate status/safety/support; no new functionality.
- [ ] Run targeted and entire pytest, verify manifest, all four CI jobs. Verify old source/evidence paths unchanged. Review once.

## Task 2: Streamlit presentation (after Task 1 and visual brief)
New dashboard/app.py and tests/v4/test_dashboard.py, separate pinned V4 requirements and launch instructions. Display evidence status/metrics/filters and locked upcoming/results/model/data health empty states; no fake real data or side effects. UI AppTest, rendered browser screenshot and Windows smoke; missing UI tooling -> BLOCKED_VISUAL_QA not PASS. No scheduler or ingestion. Stop after S1 acceptance; only then S2. Do not install UI dependencies or implement UI in this RED commit.

Review focus: corrupt/missing evidence, wrong dataset scope, matched support/tie semantics, offline side effects, clear historical vs prospective labels. Test 1 covers first three; UI test covers label/empty/error states and no job action.
