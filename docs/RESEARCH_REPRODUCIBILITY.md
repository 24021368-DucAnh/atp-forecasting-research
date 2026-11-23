# Research reproducibility and audit scope

## Why this step exists

The ATP 2026 historical report compared XGBoost, Elo and no-vig historical odds.
The saved metrics alone do not tell us which code, input bytes, ML dependency versions,
or minimum sample constraints produced them. This check adds those missing controls.

The replay command answers **one** question:

> Given the exact saved report, identical source files in the same order,
> same Python and ML package versions, and the same model source code,
> does a fresh fit and calibration produce the identical research report?

This is stronger than comparing the original file SHA-256 alone. It is still **not**
an independent model validation or a tradable T-60 backtest.

## First use on Windows (PowerShell 5.1)

Run from the existing `atp_selective_gate` project directory after this PR is merged:

```powershell
git pull --ff-only
.\.venv\Scripts\python.exe -m pytest -q

# The old 2026 report predates this source/environment manifest.
# Rebuild one report under the current research code:
.\.venv\Scripts\python.exe -m atp_gate research-train data\ATP_2026.csv --out reports\ATP_2026_reproducible.json

# Refit and compare the full report:
.\.venv\Scripts\python.exe scripts\replay_research.py reports\ATP_2026_reproducible.json data\ATP_2026.csv
```

Input files are never uploaded to GitHub. For several seasons, list **all** source files
in the same order for both training and replay.

## Output and meaning

- `status: REPRODUCED` and exit code **0** mean identical source bytes,
  recorded Python/ML package versions and code fingerprint, and a fully equal JSON
  report after refitting under the recorded thresholds and random seed.
- `status: REJECT` and exit code **2** mean provenance missing, mismatch, tampering,
  replay failure or non-identical output. No report is certified.
- In either case, `allocation_enabled=false`, `stake=0`,
  `validation_report_trusted=false` and `live_eligible=false`.

Reports now include:
- `execution_environment.python` (major/minor), package versions for numpy,
  pandas, scikit-learn, xgboost, openpyxl and pydantic, and normalized SHA-256 of
  model/data/feature source files.
- `training_configuration.minimum_total`, `minimum_target`, plus the existing seed
  and hyperparameters.
- `holdout_target.tier_counts` and actual observed `tiers`. The separate
  `configured_target_tiers` field lists all configured eligible targets, even if
  some tiers are absent from the observed holdout.

## Hard limitations

1. **No independent authenticity:** a malicious actor with write access to the report
   and source repository could change both. The code fingerprint is not a signed release.
2. **No external price verification:** source rows are day-only historical match results
   with unverified Bet365 odds timing, so none are verified T-60 quotes.
3. **No market edge certification:** repeating a log loss or Brier score does not
   show positive expected value; no wagering or API execution is enabled.
4. **No guarantee across changing versions:** differing Python or ML package versions
   yield `REJECT`. Rebuild a report after an intentional dependency/code update,
   recording that it is a new research experiment rather than overwriting the old one.
5. **Historical data may be licensed or incomplete:** preserve lawful provider terms
   and record data coverage separately. Do not commit datasets or local reports.

To interpret your prior 121-match ATP 2026 result: the odds-market benchmark beat
Elo, which beat calibrated XGBoost on that particular partial-season holdout.
A reproducible replay makes those figures more auditable, **not** more profitable.
