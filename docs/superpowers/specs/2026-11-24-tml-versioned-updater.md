# P1.5 — Versioned TML Public ATP CSV Refresh, Personal Noncommercial (2026-11-24)

## Purpose
User uses ATP predictions for **private noncommercial research only** and wants a public source updated on an ongoing basis. TennisMyLife publishes a free ATP season CSV and documented `/api/data-files` download list with daily updates. Do not scrape pages or redistribute raw CSVs; use only the publisher's direct CSV endpoint at a modest cadence. Changes to historical records can be silent; preserve immutable revisions so results can be reproduced.

## Options
1. Overwrite `2026.csv` in place every run — easy but corrupts reproducibility; rejected.
2. Let GitHub Actions fetch and commit raw vendor CSV to repo — creates raw redistribution, repo churn and permissions risks; rejected.
3. **Selected**: explicit local opt-in updater `tml-update` using the publisher's direct HTTPS season CSV, 24-hour minimum check interval, immutable SHA-256-named private local snapshots, atomic per-year metadata index and no automatic training. Provide a Windows Task Scheduler command so personal computer can run automatically once daily when powered on. Optional GitHub-only **metadata** monitoring is a future design, not included in this patch.

## Functions
- `update_tml_season(year: int, root: Path, *, at: datetime, fetcher: Callable[[str], bytes] | None = None, force: bool=False) -> dict` in `src/atp_gate/tml_snapshot.py`. Source URL **must be generated internally** as `https://stats.tennismylife.org/data/{year}.csv` and domain checked after HTTPS redirects. Never fetch arbitrary caller-provided URLs.
- Only integer season years 1968 through UTC `at.year` (or earlier). Reject future years and naive times. No API key. Documented personal use only.
- Direct download once at most per 24h, unless caller explicitly uses `--force`. Never retry in a tight loop; a failed fetch is a failure and does not advance last-successful-check marker.
- Network fetch max 20 MiB, fail on HTTP/non-UTF8/invalid CSV schema. Validate exactly the known 50 TML columns (current schema), at least one outcome row, valid `tourney_date` prefix for requested year, unique `(tourney_id, match_num)`, distinct player IDs; reject HTML responses and incomplete downloads. A live partial current season may have ongoing, missing postmatch stats; require only winner/loser IDs for completed season CSV rows.
- Storage `data/tml/<year>/<year>-<64-hex-digest>.csv` under already-ignored `data/`; no data committed. `data/tml/<year>/index.json` stores latest SHA, latest check time UTC, current version basename, source URL, row count, schema hash. Existing prior files immutable; same SHA is `UNCHANGED`, new SHA is `NEW_SNAPSHOT_REVIEW_REQUIRED` (not model-ready). Atomically update index after writing new immutable snapshot. Refuse an existing same-name file that has wrong content.
- Return only safe metadata in JSON: year, source_url, status, sha256, row_count, local snapshot path, last checked; `mode=PERSONAL_NONCOMMERCIAL_RESEARCH`, `eligible_for_model_training=0`, `allocation_enabled=false`, `stake=0`. Local path is user environment only and must never be published automatically.
- CLI: `python -m atp_gate tml-update --year 2026 --root data/tml [--force]`. A subsequent `tml-february-audit` with the separately versioned 2024 file is a different step. No implicit dataset joins or training/odds consumption.

## Security / quality
- Fixed host and HTTPS; bytes size cap; timeout; standard CA validation; no external host redirects; no TLS disable.
- No raw CSV in GitHub, issues, public PR or results report. Provider's currently published noncommercial personal research rights apply; record source URL and attribution. Source updates are untrusted until quality audit and independent official match/draw comparison.
- Only a personal owner can schedule local Windows tasks; do not claim a desktop scheduled task is installed by committing instructions.
- Handle partial download, invalid UTF8, malformed/duplicate row, overly frequent requests, empty current-season file, stale timestamps and conflicting existing snapshot.
- Combined PR stacking: this branch is based on P1 TML historical candidate PR #27; do not merge directly to `main` before #27.

## Verification
RED tests first, then implementation; full pytest and GitHub Actions 4/4 matrix. No real remote network in CI. No background execution until explicit local schedule is enabled by the user.
