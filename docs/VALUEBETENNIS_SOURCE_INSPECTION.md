# Valuebetennis multi-season inspection — P1.2

This command is a **schema, stable-ID and data-quality preflight**, *not* a model adapter, training operation, market-edge demonstration or T−60 check.

## Provider contract

Source: [Valuebetennis open data](https://www.valuebetennis.com/en/donnees.htm).

The provider publishes semicolon-separated CSVs since 2021 and explicitly states a Creative Commons Attribution 4.0 licence. Attribution required:

> Valuebetennis, Tennis results and odds since 2021, https://www.valuebetennis.com/en/donnees.htm

Provider fields include `match_id`, UTC `date`, `tournoi`, `tournoi_id`, `categorie`, `genre`, `surface`, `tour` (numeric round 0–12), `joueur1`, `joueur1_id`, `joueur2`, `joueur2_id`, `vainqueur_id` and opening/closing Pinnacle odds. **Keep the season CSVs local** under `data/`. The repo does not download or ship provider data.

## PowerShell 5.1 (project root)

After GitHub PR merge and `git pull --ff-only`, download the genuine provider annual CSVs from the above page into `data\`. Then:

```powershell
.\.venv\Scripts\python.exe -m atp_gate valuebetennis-profile --start-year 2022 --end-year 2026 data\valuebetennis-matchs-2022.csv data\valuebetennis-matchs-2023.csv data\valuebetennis-matchs-2024.csv data\valuebetennis-matchs-2025.csv data\valuebetennis-matchs-2026.csv
```

Do not interpret a successful `INSPECTED_UNMAPPED` as model readiness. Do not alter filenames or infer undocumented mapping. If one CSV is absent, the command reports missing observed years and returns a nonzero exit code (`INCOMPLETE`). Invalid source schema also exits nonzero.

## What the report is designed to show

- Raw row count; WTA/non-main-circuit exclusions; invalid match/player/winner IDs; malformed UTC date/round; duplicate match IDs
- Accepted provisional ATP `Main tour`/`Masters`/`Grand Slam` rows and observed year/category/surface coverage
- Verified locally computed SHA-256 and byte sizes for each CSV (not authenticated download origin)
- Distinct provider player IDs, number of IDs with multiple display aliases and number of ambiguous display names used by multiple IDs
- Missing or invalid opening and closing odds *pairs*, with **no odds imputation**
- Hard flags: `tier_mapping_verified=false`, `main_draw_verified=false`, `t60_quote_verified=false`, `eligible_for_model_training=0`, `allocation_enabled=false`, `stake=0`

## Important unresolved checks (next PRs)

1. Inspect at least one *actual* provider CSV to establish column spellings, encoding, timestamp format, and round semantics. CI fixtures are synthetic and do not prove vendor compatibility.
2. Establish an independent source-backed **per tournament-season** verified ID → ATP250/ATP500/Masters/Grand Slam tier registry. Never map all `Main tour` to one tier.
3. Establish main-draw eligibility from reliably documented round and tournament metadata, rather than assuming `tour >= N` is always sufficient.
4. Verify provider player IDs are stable through year transitions; warn on a name attached to multiple IDs.
5. Keep opening/closing odds outside prediction features and never label them T−60. Match timestamp is provider-supplied UTC, not independently verified actual start time.
6. Only after these gates, build a separate ID-keyed multi-year research adapter and chronological walk-forward splits. Do not mix this source with the existing name-keyed Tennis-Data historical model.

## Why not plug into XGBoost yet?

A silently misclassified `Main tour` ATP250 as ATP500 or a qualifier as main-draw would contaminate both the intended selection set and the out-of-time evaluation. Repeatability of results does not cure this measurement error. The safest correct current behavior is **ABSTAIN / no training authorization**.
