# ATP Selective Forecasting — V0.2.1 (Windows-ready, ATP index parser fix)

**Status:** research-only Python project, V0.2.1 hotfix. The `ATP` field in tennis-data CSV denotes a season-local tournament ordinal, not the ATP-tour type. V0.2 wrongly discarded all records except `ATP=1`. V0.2.1 accepts valid positive tournament ordinal IDs and classifies tiers through `Series` only. See `docs/BUGFIX_V0.2.1.md`.

**Status:** research-only Python project. The previous V0.1.1 strict, fail-closed paper selection gate is preserved; V0.2 adds an offline ATP data / pre-match feature / XGBoost calibration pipeline. **No real-money actions, no live T−60 odds, no validated market edge.**

## Install — Windows PowerShell 5.1

Install Python 3.11 if necessary. Extract this ZIP; open PowerShell in the `atp_selective_gate` directory:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test,ml]"
.\.venv\Scripts\python.exe -m pytest -q
```

`tzdata` installs automatically on Windows (fixes `Asia/Bangkok`). If the project root has moved, open PowerShell there before running these commands. A correct test run confirms the code's contracts, not a profitable strategy.

## A. Run the original V0.1 risk/input gate

```powershell
.\.venv\Scripts\python.exe -m atp_gate evaluate examples/synthetic_unvalidated.json
.\.venv\Scripts\python.exe -m atp_gate audit examples/historical_toy.csv
```

The demo must remain `ABSTAIN`/`stake: 0` with unverified model reasons. The default trusted validation-report registry remains **empty**. Do not modify this to force positive allocations.

## B. Run the new research pipeline on a reproducible SYNTHETIC sample

The file `examples/research_synthetic.csv` is fictional test data; results are not ATP performance.

```powershell
.\.venv\Scripts\python.exe -m atp_gate research-audit examples/research_synthetic.csv
.\.venv\Scripts\python.exe -m atp_gate research-train examples/research_synthetic.csv --out reports\synthetic_research.json --minimum-total 90 --minimum-target 20
```

Reports contain chronological train/calibration/holdout dates, score comparisons and `live_eligible=false`, `allocation_enabled=false`, `stake=0`.

## C. Research with real historical ATP data (not bundled)

Option 1: open `https://github.com/owenparris/tennis` and review rights/coverage, then download their historical `2026.csv` to the `data` folder, or run the included PowerShell downloader:

```powershell
.\scripts\download_atp_2026.ps1
.\.venv\Scripts\python.exe -m atp_gate research-audit data\ATP_2026.csv
.\.venv\Scripts\python.exe -m atp_gate research-train data\ATP_2026.csv --out reports\ATP_2026_research.json
```

If PowerShell blocks `.ps1` scripts, **do not change the execution policy**: open the source URL in a browser, save the CSV as `data\ATP_2026.csv`, then run the two Python commands. The verified public 2026 snapshot contains 1,016 records dated January 4–May 3: 984 Completed, 25 Retired and 7 Walkover. After the V0.2.1 index fix, `research-audit` should accept 984 completed rows, of which 694 are from Grand Slam/Masters1000/ATP500 and 290 ATP250 contribute to player history. This is a partial year: even if a model trains, its one-season holdout must not be treated as persistent edge. Never relax validation thresholds to force a result.

Option 2: acquire the ATP season files from `https://www.tennis-data.co.uk/data.php` in `.xlsx` format; the new loader accepts them directly:

```powershell
.\.venv\Scripts\python.exe -m atp_gate research-train data\2023.xlsx data\2024.xlsx data\2025.xlsx data\2026.xlsx --out reports\atp_multiseason_research.json
```

Download names depend on the provider. Files are **not provided** in this ZIP; obey the providers' terms and check whether a file's contents and date precision actually match the expected schema. You may also pass multiple `.csv` files in one command. Training/replay use all recognized ATP250/500/Masters/Slams for history; target holdout evaluation is only ATP500/Masters/Slams.

## C2. Verify research report provenance (after generating a report)

The following checks that the input files are byte-for-byte identical to the
SHA-256 manifest recorded in a historical report, and that the report remains
research-only. It does **not** rerun the model or validate an odds edge.

```powershell
.\.venv\Scripts\python.exe -m atp_gate research-verify reports\ATP_2026_research.json data\ATP_2026.csv
```

Expect `status: MATCH` on an unchanged source, or a nonzero exit code and
`status: REJECT` if mismatched. See `docs/EXPERIMENT_INTEGRITY.md`.

## What V0.2 actually does

1. `research_data.py` validates historical winner/loser CSV/XLSX, supported categories, surfaces, format, completion status, odds/overround and duplicate match keys. Canonical A/B side is alphabetical, **not winner-first**. Audits skipped and incomplete rows.
2. `research_features.py` replays the MIT upstream-style overall+surface Elo, short recent form, H2H, rest and rank using prior **calendar days only**. All matches of one day receive frozen pre-day features before any outcomes from that day are absorbed. It produces 18 upstream-compatible feature names, but unavailable historical serve/return features stay missing (`NaN`), not invented.
3. `research_train.py` fits XGBoost on the first ~60% of eligible **unique dates**; fits a separate sigmoid (Platt) calibrator on the next ~20%; evaluates against Elo on the final ~20%; compares against no-vig historical market odds on identical rows where prices exist. It DOES NOT use odds or outcomes as input features, does not train calibrators on holdout results, and does not generate a trusted model report.
4. `__main__.py` exposes `research-audit` and `research-train`. The prior `evaluate` and `audit` commands remain backward-compatible.

## Critical limitations and next milestone

- Historical two-sided odds in `tennis-data` format often have no quote timestamp; therefore historical comparisons **are not T−60 backtests or executable stakes**.
- Research-only source name strings are not verified player IDs, and source match date is not an actual match start time. No feature adapter into `DecisionInput` is permitted yet.
- Serve/return statistics are missing in this input format. XGBoost handles missing research columns, but such a prediction cannot pass V0.1's stronger live feature contract without reliable pre-match stats and aligned training/inference.
- The existing upstream model readme reports that its classifier beats raw Elo but does **not** beat the market's closing odds. Report results objectively; selecting the best ROI threshold on the holdout is overfitting.
- A single time split is an initial checkpoint, not multi-year rolling walk-forward nor statistically conclusive model validation; future versions must add season-by-season retraining, stable player IDs, actual quote snapshots, confidence intervals, and independent evidence approval.

For design, test plan, and source-rights audit see `docs/superpowers/specs/2026-11-23-research-pipeline-design.md`, `docs/superpowers/plans/2026-11-23-research-pipeline.md`, and `docs/THIRD_PARTY_NOTICES.md`.


## D. Replay a saved historical experiment

New research reports record exact source checksums, actual observed target-tier
counts, training sample thresholds, model-source fingerprint and ML dependency versions.
The replay command refits the model under these inputs and requires identical output.
Old V0.2.1 reports do not contain the required environment information, so generate
a new report first:

```powershell
.\.venv\Scripts\python.exe -m atp_gate research-train data\ATP_2026.csv --out reports\ATP_2026_reproducible.json
.\.venv\Scripts\python.exe scripts\replay_research.py reports\ATP_2026_reproducible.json data\ATP_2026.csv
```

Successful replay reports `status: REPRODUCED`. A mismatch returns
`status: REJECT` and a nonzero exit code. Neither result grants permission
for live wagers or capital allocation; there are still no verified T-60
price snapshots. See `docs/RESEARCH_REPRODUCIBILITY.md`.


## P1.1 — Profile historical source coverage (no model training)

`research-profile` inventories **accepted matches only** using the same
existing loader as `research-train`. It groups by actual observed year, tier,
surface and original file, with missing odds/rank counts, SHA-256 manifest,
dropped-duplicate counts and explicit source/rights warnings.

After this PR is merged, from the original Windows PowerShell project folder:

```powershell
git pull --ff-only
.\.venv\Scripts\python.exe -m atp_gate research-profile data\ATP_2026.csv
```

To require multiple specific calendar years:

```powershell
.\.venv\Scripts\python.exe -m atp_gate research-profile --start-year 2022 --end-year 2026 data\ATP_2026.csv
```

The second command **must** print `status: INCOMPLETE` and exit with code 2
when only the partial 2026 file is supplied. This is a correct failure and
does NOT mean the system is broken. To profile multiple seasons, provide
**actual**, legally obtained, schema-compatible source files in year order.

A profile does not verify data rights, stable player IDs, first-serve times,
T−60 odds, sample completeness, or any market edge. Do not supply a
Valuebetennis CSV directly to the current Tennis-Data-style loader; its schema
and ATP 250/500 taxonomy need a separately validated adapter. See
`docs/DATA_SOURCE_DECISIONS.md`.


## P1.2 — Inspect licensed Valuebetennis ATP identity/coverage (no model training)

Provider: https://www.valuebetennis.com/en/donnees.htm (CC BY 4.0 with attribution).
Its annual exports are semicolon-delimited ATP/WTA singles CSVs with
`match_id` and player IDs. **Do not** feed these CSVs into `research-train`;
the `Main tour` label does not identify ATP250 vs ATP500 and `tour` is
a numeric draw round, not the ATP/WTA circuit. The provider's opening and
closing odds are **not** timestamped T−60 snapshots.

When this PR is merged and you have downloaded provider files to `data/`:

```powershell
git pull --ff-only
.\.venv\Scripts\python.exe -m atp_gate valuebetennis-profile --start-year 2022 --end-year 2026 data\valuebetennis-matchs-2022.csv data\valuebetennis-matchs-2023.csv data\valuebetennis-matchs-2024.csv data\valuebetennis-matchs-2025.csv data\valuebetennis-matchs-2026.csv
```

`INSPECTED_UNMAPPED` means source rows and IDs were inventoried. It is
**not** player-ID verification against an independent authority, match main
draw verification, provider-file origin authentication, official tier mapping
or market edge verification. The report always keeps
`eligible_for_model_training: 0`, `allocation_enabled: false`, `stake: 0`.
See `docs/VALUEBETENNIS_SOURCE_INSPECTION.md`.


## P1.3a — Inventory Valuebetennis tournament IDs and draw-round codes

The provider's `Main tour` category does **not** certify ATP250 vs ATP500,
and its `tour` 0–12 code does not automatically prove a main-draw round.
Generate an inspectable per-season/per-tournament ID catalog, keeping raw
categories, round distributions, source hashes and unresolved collisions:

```powershell
.\.venv\Scripts\python.exe -m atp_gate valuebetennis-tournaments --out reports\valuebetennis_tournaments_2022_2026.json --start-year 2022 --end-year 2026 data\valuebetennis-matchs-2022.csv data\valuebetennis-matchs-2023.csv data\valuebetennis-matchs-2024.csv data\valuebetennis-matchs-2025.csv data\valuebetennis-matchs-2026.csv
```

The command prints a compact status and saves its full JSON under the
git-ignored `reports/` folder. `INVENTORIED_UNMAPPED` means a source
inventory was generated, **not** that ATP tier, qualifiers/main draw or
T−60 market odds were verified. For schema, limitations and next official
mapping work, see `docs/TOURNAMENT_SEASON_INVENTORY.md`.


## P1.3b — Diagnose calendar-year splits and missing match stages

Review the **already exported** `valuebetennis-tournaments` JSON (no need to
re-read five annual CSVs):

```powershell
.\.venv\Scripts\python.exe -m atp_gate valuebetennis-review reports\valuebetennis_tournaments_2022_2026.json --out reports\valuebetennis_inventory_review_2022_2026.json
```

The reviewer validates group and round-count reconciliation and flags
event IDs split across UTC calendar years, special-format events wrongly
implied by broad provider categories, missing raw final-round codes and
unusually long gaps between observed in-season tournament starts.
`REVIEW_REQUIRED` means inspection succeeded while **training is still
blocked**. See `docs/INVENTORY_ANOMALY_REVIEW.md` for provider caveats,
actual 2024 anomalies and mandatory official tournament evidence.


## P1.3c — Snapshot-pinned, source-backed tournament tiers

Review a small set of **explicit** ATP tournament-tier claims in a source-
anchored registry; unresolved ATP editions are **not inferred** from provider
`Main tour` or `Masters` labels. Dallas/Doha/Munich changed from ATP250 to
ATP500 in 2025. The 2024 AO/Indian Wells entries remain **known incomplete**.

After merging the corresponding PR:

```powershell
git pull --ff-only
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m atp_gate valuebetennis-tier-audit reports\valuebetennis_tournaments_2022_2026.json docs\registries\valuebetennis_2022_2026_tiers_v1.json --out reports\valuebetennis_tier_audit_2022_2026.json
```

A mismatched source SHA-256 exits nonzero. `REVIEW_REQUIRED` means the
audit completed, **not** that official tournament editions, main-draw
eligibility, full match coverage or T−60 market quotes were established.
This does not train a model. Full interpretation and source URLs:
`docs/TIER_REGISTRY_AUDIT.md`.


## P1.4a — Identify missing official ATP events before multi-season model training

An independently researched ATP 2024 February calendar contains **12 tournaments**
(eight ATP 250, four ATP 500) that did not appear in the pinned Valuebetennis
tournament inventory. To independently reproduce the **read-only** gap audit:

```powershell
git pull --ff-only
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m atp_gate valuebetennis-calendar-audit reports\valuebetennis_tournaments_2022_2026.json docs\registries\atp_2024_february_official_events_v1.json --out reports\valuebetennis_official_calendar_audit_2024_feb.json
```

`COVERAGE_REVIEW_REQUIRED` is the expected audit status, not a data/model
approval. The official reference covers **February 2024 only**; matching
by city/time is a review candidate rather than a verified ID, and absent
results must not be imputed. Opening/closing prices are not verified T−60
odds. See `docs/OFFICIAL_CALENDAR_COVERAGE.md`.
