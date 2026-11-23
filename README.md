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
