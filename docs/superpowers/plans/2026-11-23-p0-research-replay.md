# P0 Experiment Reproducibility — Design & Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans (or subagent-driven-development) task-by-task; write tests first, verify red, implement, and verify green.

**Goal:** Make each historical ATP research report inspectable and replayable against its original input bytes, model code and ML dependency versions.

**Architecture:** V0.2.1 model training stays historical-only. Attach execution metadata and actual holdout tier counts to reports. Replaying recomputes the report with exactly the recorded parameters after verifying input hashes, source order, environment and local model source fingerprint; it rejects on mismatch without ever treating research as model approval.

**Tech Stack:** Python >=3.11, stdlib hashlib/importlib.metadata, current pandas/scikit-learn/XGBoost stack, pytest.

**Spec:** `docs/superpowers/plans/2026-11-23-p0-engineering-foundation.md` Task 2; research-only safety constraints.

## Global constraints
- Preserve CLI `research-train`, `research-audit` and current training settings.
- Keep `data/` and `reports/` untracked; no bundling of historical data or credentials.
- All replay outputs carry `allocation_enabled=false`, `validation_report_trusted=false` and `stake=0`.
- Verified replay is NOT market validation, live odds validation, an independent audit, or proof of edge.
- Old V0.2.1 reports without an environment fingerprint cannot be fully replay-verified. They must be regenerated under the new code.

## Review focus
- Reordering source files can change duplicate handling even when their hashes match; require the same source order.
- Package/version drift makes an otherwise identical input non-comparable; fail closed.
- User-modified result fields must be detected even if data hashes still match.
- Mismatched or missing inputs must be rejected before fitting an XGBoost model.
- Code changes can alter metrics without changing the dependency versions; stamp a normalized code fingerprint.

## Task 1 — Report metadata and correct target tiers
**Files:** `src/atp_gate/research_train.py`, `tests/test_research_replay.py`
- [x] Specify failing tests for actual target-tier counts and dependency/parameter metadata.
- [ ] Run CI and confirm failures.
- [ ] Add observed tier counts, seed/minimum thresholds and environment/code fingerprint.
- [ ] Re-run tests.

## Task 2 — Historical replay verification
**Files:** `src/atp_gate/research_replay.py`, `tests/test_research_replay.py`
- [x] Write missing-module and safety/tampering tests first.
- [ ] Observe missing-module red in CI.
- [ ] Verify input set/order/digest and environment, replay report, compare all research outputs.
- [ ] Re-run tests and inspect failure details.

## Task 3 — Windows entrypoint and documentation
**Files:** `scripts/replay_research.py`, `docs/RESEARCH_REPRODUCIBILITY.md`
- [ ] Add a small CLI that takes a saved report and original files; failure must exit nonzero.
- [ ] Document first-time regeneration of old V0.2.1 reports and strict limitations.
- [ ] Confirm four CI jobs pass on Ubuntu and Windows, Python 3.11/3.12.

## Acceptance
PR remains draft until four green CI jobs. Merging is a separate user review/decision.
