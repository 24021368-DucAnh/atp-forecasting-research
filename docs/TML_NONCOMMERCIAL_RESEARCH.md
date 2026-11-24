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

## Opt-in automatic local source snapshots (P1.5)

Once the stacked updater PR is merged and the Windows venv has the package installed, run manually:

```powershell
.\.venv\Scripts\python.exe -m atp_gate tml-update --year 2026 --root data/tml
.\.venv\Scripts\python.exe -m atp_gate tml-update --year 2024 --root data/tml
```

Each command downloads **directly from the official TML CSV endpoint** only when explicitly invoked. The default cache limit is one check per 24 hours per season. If the bytes match the last snapshot, status is `UNCHANGED`; if they differ, `NEW_SNAPSHOT_REVIEW_REQUIRED` is written. Older snapshots are never silently replaced. Snapshot files live privately under `data/tml/<year>/<year>-<SHA256>.csv`; the `index.json` stores the latest digest and check timestamp. `data/` and `reports/` are ignored by Git. Never commit these third-party raw files.

### Local Windows Task Scheduler option

The versioned update script is `scripts/tml_daily_update.ps1`. It checks 2024 for historical corrections and the current year for ongoing results. To run daily **on the owner's computer**, create a Task Scheduler task with:

- Trigger: Daily, e.g. 08:30 Hanoi time, only when the PC is available.
- Action program: `powershell.exe`.
- Action arguments: `-NoProfile -File "C:\path\to\atp_selective_gate\scripts\tml_daily_update.ps1"` (replace with the actual repo path).
- Working directory: the local repo. User should ensure the local virtual environment exists and the installed source is up to date.

This configuration is a **user action**. Committing a script does **not** install or start a scheduled task, and a powered-off PC cannot refresh local data. The script creates per-run *metadata only* reports under `reports/tml_updates/`. It does not upload raw CSV, train a model, or connect to gambling systems.

For each new 2024 hash, run `tml-february-audit` on the **hash-qualified snapshot** (supported by the updater branch) before considering any source corrections. The report remains `SOURCE_CANDIDATE_REVIEW_REQUIRED` unless the provider changes the event/rounds, in which case it flags inconsistencies. Both results are still untrusted for official-draw certification and point-in-time match timing.

### Provider updates and drift

The publisher states that corrections, additions and removals may occur, including historical seasons. A new hash therefore represents a new data version, not necessarily more matches. Compare the exact source SHA and source rows before discussing model improvements; preserve all previous experiment inputs. New match results become available after the event, not as future-known prematch features.

The official source updates are for personal/educational/noncommercial research. No automated redistribution of CSVs and no public model service are permitted by the source's stated terms.

### Important source anomaly handling

A public CSV may have incomplete provider match identifiers. In the archived TML GitHub `2025.csv` examined on 2026-11-24, **489 of 2,944 rows had blank `match_num`**, and one trailing row was shorter than the 50-column schema. The `2025.csv` source also legitimately starts with tournaments dated **2024-12-29**. These observations are for the GitHub historical snapshot; the official website's current bytes may differ.

`tml-update` **preserves all original bytes** at their content SHA even if the source contains such row defects, but records `source_anomalies` and `accepted_rows` in `index.json` and reports `SOURCE_ANOMALY_REVIEW_REQUIRED`. This is a *quarantine*, not source approval. The watcher explicitly flags anomalies for manual review. No synthetic match ID is created. Subsequent research code may exclude these rows with counted losses of coverage, but may not silently assert that all events were complete.

A new source SHA or a successful CSV download does **not** mean the model training or money-allocation gate is unlocked. Official draw comparison, historical availability timing and market quotes remain independent evidence requirements.

## February 2024 cross-publication comparison with Sackmann archive

A separate historical file is publicly archived at [Aneeshers/tennis-sackmann-archive](https://github.com/Aneeshers/tennis-sackmann-archive/blob/main/atp/atp_matches_2024.csv), which attributes its source to Jeff Sackmann and uses CC BY-NC-SA 4.0. Use it only within the personal, noncommercial research scope and keep provider CSVs private.

**Source lineage warning:** TML and this Sackmann archive may derive from overlapping historical inputs. Agreement between them is **not independent official ATP verification**. TML's 2024 snapshot uses 50 columns and alphanumeric player IDs, whereas the Sackmann archive uses 49 columns and numeric player IDs. Tournament IDs also differ in leading-zero formatting, and source-local `match_num` values are not globally portable. **Do not perform naive joins on either player ID or match_num across these providers.**

On pinned public GitHub snapshots reviewed 2026-11-24 (TML Git blob SHA-1 `cf513429259b4a15e84e2021206895d9bd4ff772`, Sackmann archive blob `c401319bc1dec4633dd2c730aa5a7a7376e176f8`), the twelve mapped February 2024 ATP tournaments provided **340/340** matches agreeing on event/winner/loser/round after an explicitly reviewed name alias mapping. **339/340** score strings agreed byte-for-byte; the exception was a Buenos Aires quarterfinal retirement reported as `4-6 7-5 RET` vs `4-6 7-5 0-0 RET`. Neither representation proves a played third set.

The repository pins those **two observed name variants only** in `docs/registries/tml_sackmann_2024_player_aliases_v1.json`. No automatic fuzzy matching or claimed ATP canonical player ID mapping is allowed. The local audit tool `tml_sackmann_crosscheck.py` checks the two raw files **without uploading them** and returns aggregate match/score consistency and SHA-256 hashes.

After obtaining the private 2024 source files on the computer, run:

```powershell
.\.venv\Scripts\python.exe -m atp_gate tml-crosspublication-audit `
  data\tml\2024\2024.csv `
  data\sackmann\atp_matches_2024.csv `
  docs\registries\tml_2024_feb_source_crosswalk_v1.json `
  docs\registries\tml_sackmann_2024_player_aliases_v1.json `
  --out reports\tml_sackmann_2024_feb_crosscheck.json
```

Replace the displayed TML path with its real SHA-named snapshot path if using the versioned updater. Never copy a third-party raw CSV into a GitHub PR or reports artifact.

Even `CROSS_PUBLICATION_AGREEMENT_REVIEW_REQUIRED` means **only** that these publications agree, not that the ATP's official match draw or match timestamps have been verified. A trusted actual odds T−60 or profitable trade remains unsupported. Source audit flags always set `eligible_for_model_training=0`, `allocation_enabled=false`, `stake=0`. See [P1.4d Issue #17](https://github.com/24021368-DucAnh/atp-forecasting-research/issues/17).
