# P2B — ATP Elo historical skill experiment (TennisMyLife, personal research)

This experiment uses openly obtainable **personal, educational, noncommercial** TML historical ATP singles records, with source attribution and locally pinned SHA-256s. It does **not** redistribute source CSV, train a trusted production model or generate betting recommendations.

**Purpose:** test whether pre-tournament Elo ratings, computed exclusively from older tournament results, distinguish eventual match winners across three historical calendar-year holdouts. This is a *retrospective conditional-matchup* skill study, not a live prediction of which two players will actually meet in a later round.

## Prerequisites and local run (Windows PowerShell)

Once dependency PRs #27 and #28 and this PR are merged and the local `.venv` is refreshed:

```powershell
# From the project's atp_selective_gate directory:
foreach ($year in 2021..2025) {
    .\.venv\Scripts\python.exe -m atp_gate tml-update --year $year --root data/tml
    if ($LASTEXITCODE -ne 0) { throw "TML source update failed for $year" }
}

$sourceFiles = @()
foreach ($year in 2021..2025) {
    $index = Get-Content "data/tml/$year/index.json" -Raw | ConvertFrom-Json
    $sourceFiles += "data/tml/$year/$($index.snapshot_filename)"
}

.\.venv\Scripts\python.exe -m atp_gate tml-elo-experiment $sourceFiles --out reports/tml_elo_2021_2025.json
```

Alternatively, `scripts/run_tml_elo_research.ps1` reads already locally stored verified snapshot indices and runs the experiment **without downloading**. Do not upload provider CSVs or publish match-level derivative tables. No automatic model training is scheduled by the source-monitor workflow.

## What is actually known at the prediction cutoff

- TML's `tourney_date` records **tournament beginning**, NOT an individual match's date/time. No observed T−60 odds, verified lineups at event start, or actual first serve.
- The Elo predictor uses **only stable player IDs, tournament start, tournament surface and previously matured match results**. It never uses winner-first feature orientation, winner/loser stats, final-round score, rankings recorded later in the event, or retrospective final score as a predictor.
- Player A is the **lexicographically smaller** stable player ID. The outcome is 1 if this player won, 0 otherwise; otherwise a winner-first CSV would leak the target directly.
- Outcomes of all matches in a tournament are quarantined until **28 days after that tournament's start**. Ratings are frozen when evaluating every eventual matchup in that tournament. Events starting together are updated in one result batch, not depending on arbitrary row order. This is a conservative approximation to historical result publication, **not proof** the individual result was actually published exactly then.
- TML's season 2025 may include event start date 2024-12-29. Chronological fold year follows the **event start calendar year**, not the nominal season CSV filename.

## Fixed baselines and metrics

- Overall Elo starts at 1500 and applies `K=24` to each valid matured match.
- Surface-shrunk Elo combines overall Elo with the pre-start hard/clay/grass Elo using fixed `surface_weight=0.35`, shrinkage `n/(n+20)`. These are *precommitted hypotheses*, not holdout-tuned optima.
- Raw research includes ATP event source tiers `250`, `500`, `M`, `G`. Ambiguous `A` and other categories are excluded and counted; do not infer their official tier from a vendor code. Retirements, walkovers and incomplete results are excluded and counted.
- Three disjoint holdout calendar years by default: **2023, 2024, 2025**. Older 2021–2022 data provides warmup. Updates from an earlier holdout tournament enter later forecasts only after the 28-day embargo; this is sequential prequential evaluation, not an unconditional fixed-model holdout.
- All three predictors (50/50, overall Elo, surface Elo) score **the same matches**. Brier and log loss are lower-is-better. A deterministic tournament-cluster bootstrap gives only a descriptive 95% interval when at least 12 event groups are present and at least 2 per fold. This is not a guarantee of population-level uncertainty under data selection/drift.
- No independent **market no-vig odds** are present, so outperforming the 50/50 baseline is **NOT evidence of beating sportsbooks or positive expected value**.

## Artifacts and reproducibility

The report contains source year, original source filename, SHA-256, bytes and row count, filtered/excluded-match counts, fold and aggregate metrics and explicit warnings. It **does not serialize raw match rows, names, fixture IDs or winner labels**. All original source snapshots remain under gitignored `data/tml`, not GitHub.

A source hash change means a different experiment. Compare metrics only on equal data provenance and equal event/player sets. Use an external independent official draw audit before discussing model certification. Historical value betting and paper money are separate P3/P0 work.

All outputs explicitly declare: `status=HISTORICAL_SKILL_RESEARCH_ONLY`, `participant_known_at_event_start=false`, `source_result_availability_exact=false`, `t60_quote_verified=false`, `market_edge_verified=false`, `model_validation_trusted=false`, `allocation_enabled=false`, `stake=0`.

**Source and rights:** [TennisMyLife ATP database](https://stats.tennismylife.org/tennis-match-database), [TML GitHub terms](https://github.com/Tennismylife/TML-Database). Attribution and personal/noncommercial restriction apply. No raw CSV redistribution.

**Source readiness:** TML-2024 Feb candidate audit [#27](https://github.com/24021368-DucAnh/atp-forecasting-research/pull/27); versioned updater [#28](https://github.com/24021368-DucAnh/atp-forecasting-research/pull/28); research issue [#29](https://github.com/24021368-DucAnh/atp-forecasting-research/issues/29).
