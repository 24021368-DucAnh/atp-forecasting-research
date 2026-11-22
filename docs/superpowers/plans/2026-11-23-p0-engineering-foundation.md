# P0 Engineering Foundation — implementation plan

> **For agentic workers:** Use an isolated feature branch, ship one testable change at a time, and review a pull request before merging.

**Goal:** Replace repeated ZIP releases with a reproducible GitHub-based development and verification workflow for ATP Selective Forecasting Lab.

**Architecture:** Preserve the functional V0.2.1 code and CLI contracts. Introduce continuous integration first, then refactor directories in separately reviewed pull requests without changing research outcomes. Keep raw data and generated reports outside Git.

**Tech stack:** Python 3.11+, pytest, Pydantic, XGBoost optional ML dependencies, GitHub Actions, Windows PowerShell.

**Spec:** Established V0.2.1 README and `docs/superpowers/specs/2026-11-23-research-pipeline-design.md`.

## Global constraints

- Paper/historical-research only: never enable live allocation, default trusted model evidence remains empty.
- No training/evaluation leakage; ATP historical observations provide day precision only, never T-60 quotes.
- `data/`, `reports/`, `.venv/`, secrets, credentials and model binaries are untracked.
- All changes go to feature branches, and `main` is changed only after review and successful checks.
- Preserve V0.2.1 reference: 85 tests and the ATP_2026 holdout report should remain reproducible with the original input hash.

## Review focus

1. Windows timezone database: install `tzdata` on Windows and verify timezone-based gate tests.
2. Linux/Windows behavior: run the same pytest suite on both.
3. Python dependency compatibility: verify both 3.11 and 3.12.
4. Historical research must stay safely ineligible for live allocation.
5. Avoid committing local data, reports or credentials.

## Task 1 — CI baseline (this PR)

- [x] Create `chore/p0-ci-foundation` branch from `main`.
- [x] Add `.github/workflows/ci.yml`.
- [x] Configure Python 3.11 and 3.12 on Windows and Linux.
- [x] Install `.[test,ml]` and execute `python -m pytest -q`.
- [x] Smoke-test `evaluate` and the bundled synthetic historical audit.
- [ ] Confirm four CI matrix jobs succeed on GitHub Actions.
- [ ] Review and merge PR, only if all jobs pass.

## Task 2 — Repository reproducibility (next PR)

- [ ] Add source/environment manifest and test exact reconstruction from a fresh checkout.
- [ ] Add formatting and dependency consistency checks (without changing model behavior).
- [ ] Add workflow for documenting experiments: input checksum, configuration, train/calibration/test dates and seed.
- [ ] Confirm no machine-specific output becomes tracked.

## Task 3 — Architecture cleanup (later PR)

- [ ] Incrementally separate ingest, feature, model, evaluation and policy modules while preserving CLI compatibility.
- [ ] Add regression tests proving V0.2.1 accepted rows, splits and metrics remain consistent.
- [ ] Update Windows installation and `git pull` instructions.
- [ ] Review tests and documentation together.

## Task 4 — Multi-season ML data research (after P0)

- [ ] Inventory lawful permitted multi-season sources.
- [ ] Verify season and tournament coverage, stable player IDs, missingness, retired/walkover rules.
- [ ] Add temporal walk-forward evaluation with independent calibration and strict market comparison.
- [ ] Keep results research-only until independently verified as-of price evidence exists.

## Acceptance

P0 Task 1 is **not completed** until GitHub CI reports all expected jobs successful. A committed workflow or opened PR alone does not establish CI success.
