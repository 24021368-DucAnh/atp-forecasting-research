# V0.2.1 — Source parser regression fix (2026-11-23)

## Symptom reported on Windows

`research-audit data\ATP_2026.csv` showed 1,016 rows but only 30 accepted,
`unsupported_tier=985`, `not_completed=1`; `research-train` reported zero
eligible player-history rows. The source file fingerprint was
`a9ff61474edcdd69b14333f02cbcf6ba21b5cf24e75080e2214e507e336a0c13`.

## Root cause

`research_data.py` incorrectly treated the input's `ATP` field as an ATP-tour
indicator with accepted values `1`/`1.0`. In the source format it represents a
season-local tournament index (e.g. `5` for the Australian Open, `16` for a
Masters event). The actual tournament category is `Series`. V0.2 dropped
nearly all rows before examining that category.

## Correct semantics and change

- If a column named `ATP` exists, it is validated as a **positive integer
  ordinal**, with decimal representations like `16.0` allowed for Excel input.
  It must **not** be used to identify the player's tour or tournament tier.
- `Series` is mapped using the tier dictionary to Grand Slam, Masters 1000,
  ATP500, ATP250 (ATP250 is allowed as background history).
- A source's true ATP men's singles provenance is not proven by a positive
  tournament ordinal; keep `source_identity_verified=false` and never pass
  historical rows through the live T−60 gate.
- Regression tests were written and failed on V0.2 (0/4 accepted, wrong
  error class for invalid `ATP`) before the parser was fixed. 85/85 full tests
  pass after the fix in the local verification environment.

## Expected source-level checks

For the 184,479-byte public `2026.csv` snapshot (Jan 4–May 3):

| Field | Expected |
|---|---:|
| total_rows | 1016 |
| accepted (Completed) | 984 |
| not_completed | 32 |
| unsupported_tier | 0 |
| accepted Grand Slam | 120 |
| accepted Masters1000 | 330 |
| accepted ATP500 | 244 |
| accepted ATP250 | 290 |
| invalid or missing odds among accepted (not filtered out) | 9 |

The last five checks were calculated independently from raw source data, not
from an executed Windows audit. The user's local audit must confirm it.
`research-train` uses a min-history threshold of five prior matches per
player, measured from prior dates only; one-season training/holdout is
exploratory and is **not** a live trading authorization.

## Windows PowerShell

Unzip the V0.2.1 release into a separate folder, open `atp_selective_gate`, then:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test,ml]"
.\.venv\Scripts\python.exe -m pytest -q
New-Item -ItemType Directory -Force data | Out-Null
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/owenparris/tennis/main/2026.csv" -OutFile "data\ATP_2026.csv" -UseBasicParsing
.\.venv\Scripts\python.exe -m atp_gate research-audit data\ATP_2026.csv
.\.venv\Scripts\python.exe -m atp_gate research-train data\ATP_2026.csv --out reports\ATP_2026_research.json
```

If you want to preserve your existing V0.2 `.venv` and data folder, copy
**only** `src/atp_gate/research_data.py` from V0.2.1 into the old project's
corresponding path (after making a backup); no new dependency is required.
Then rerun the audit, tests and model research in the old project's folder.

**Never change threshold values simply to force a model training result.**
