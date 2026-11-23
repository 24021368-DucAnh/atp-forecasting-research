# TennisMyLife ATP data — private noncommercial research intake

**Status:** source audit candidate, not model-ready / no real-money wagers.

## Scope and terms

TennisMyLife (`https://stats.tennismylife.org/tennis-match-database`) publishes ATP match CSV files for personal, educational and **noncommercial** research. Its GitHub README (`https://github.com/Tennismylife/TML-Database`) explicitly restricts commercial use and redistribution of raw CSVs. This project is private noncommercial research; preserve attribution to TennisMyLife, ATP source metadata and upstream related rights. Do **not** commit, republish, re-host or sell provider raw CSVs, and do not treat a site's general MIT website/software footer as a blanket license for its raw tennis data.

The GitHub repository is a *historical snapshot*, while the provider states that the official website contains current exports with daily updates. The two must be versioned separately; never silently assume the site's `2024.csv` equals GitHub blob `cf513429259b4a15e84e2021206895d9bd4ff772`.

## Obtain one local season snapshot

PowerShell:

```powershell
New-Item -ItemType Directory -Force .\tml-data | Out-Null
Invoke-WebRequest -Uri "https://stats.tennismylife.org/data/2024.csv" -OutFile ".\tml-data\2024.csv"
Get-FileHash .\tml-data\2024.csv -Algorithm SHA256
.\.venv\Scripts\python.exe -m atp_gate tml-february-audit `
  .\tml-data\2024.csv `
  docs\registries\tml_2024_feb_source_crosswalk_v1.json `
  docs\registries\atp_2024_february_official_events_v1.json `
  --out reports\tml_february_2024_audit.json
```

The command is **read only** on all inputs; it only writes the explicit report. The repo ignores `reports/`; do not commit private provider CSV or source-derived raw rows.

You can also manually inspect `https://stats.tennismylife.org/api/data-files` as advertised by the publisher to see which seasonal exports exist. Updates are not automatically equivalent to corrected, source-certified records.

## First source reconnaissance (2026-11-24)

The GitHub snapshot `Tennismylife/TML-Database@master:2024.csv` contained:
- 3,076 rows × 50 columns, 455 rows where the **tournament date** starts in February, including Davis Cup.
- **12** mapped official ATP tour event candidates, **340** match rows: four ATP500s with 124 rows and eight ATP250s with 216 rows.
- Rotten? No: tournament keys `2024-407` Rotterdam (31 rows), `2024-424` Dallas (27 rows) and ten further event IDs are recorded in `docs/registries/tml_2024_feb_source_crosswalk_v1.json`.
- TML's raw tournament level `A` can denote ATP Tour without the ATP250/500 split; for Doha and Los Cabos the **curated 2024 ATP official tier** is ATP250. Never upgrade them to Masters by interpreting `A`.
- TML `tourney_date` is **the tournament-week/start date**; individual fixture dates, start/serve times, live odds and true T−60 executable offers are **not supplied**. This source can improve historical outcomes/point-statistics research, but cannot by itself support leakage-free fixture-by-fixture pre-match timestamps or a betting quote backtest.

The 340 rows and event/round histograms are a *candidate source reconciliation*. A complete main-draw match-level official-ID result audit is separate. The `(tourney_id,match_num)` composite is a provider match ID, not an official ATP canonical match identifier.

## Source quality report contract

`SOURCE_CANDIDATE_REVIEW_REQUIRED`: expected per-event count and round structure, basic identity and format checks agree on the audited local file — but **official draw and outcome correctness are still UNVERIFIED**.

`SOURCE_CANDIDATE_INCONSISTENT`: missing event, duplicate match, player conflict, changed source round histogram or metadata. Review anomalies and do not fix by inventing rows.

Every report records local SHA256/size, per-event counts and provider source levels. Regardless of status:
`main_draw_verified=false`, `individual_match_start_verified=false`, `eligible_for_model_training=0`, `allocation_enabled=false`, `stake=0`.

## Planned rolling updates

Use the publisher's official documented downloadable season CSVs or `/api/data-files` list; cap checks to once daily (not scraping live match pages). Each download needs an immutable **content-hash version**, source URL, downloaded UTC timestamp, source count/schema, and separate accepted/review-required status. A change of hash may reflect a correction rather than new completed matches.

Once a local source version passes quality checks, **do not auto-promote it into training**. First reconcile stable player IDs and official main-draw history, confirm chronology for point-in-time features, and pre-register P2's out-of-time test split. Source-only acceptance never upgrades model validation or trading readiness.
