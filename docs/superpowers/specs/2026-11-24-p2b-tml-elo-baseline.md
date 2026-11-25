# P2B — Private pre-tournament Elo skill baseline from versioned TML data (2026-11-24)

**Issue:** #29, parent P2 #12. **Stacked on:** P1 TML data audit #27 → versioned updates #28. **Mode:** `PERSONAL_NONCOMMERCIAL_RESEARCH`. **Never certified for betting.**

## Objective
Build a reproducible *real* offline ATP research baseline from permitted, locally stored TennisMyLife season CSVs, with no outcome leakage across tournaments and at least three disjoint out-of-time evaluation calendar years. Evaluate general and surface-shrunk Elo versus 50/50, reporting proper probabilistic metrics and no financial metrics. Every source revision is content-pinned, and no TML raw rows are committed.

## Alternatives considered
1. Sort every match by `tourney_date` and update Elo after each row — **reject**: `tourney_date` is the tournament start, not match time; this can train on finals before scoring earlier matches in the same event.
2. Claim an exact first-serve T−60 forecast from tournament-week date — **reject**: first serve and actual pre-match participant information are absent.
3. **Selected:** freeze ratings before each tournament and defer results for a full **28-day embargo after its start date**; evaluate only eventually observed matchups, explicitly labeling their identities as retrospectively selected. Do not infer odds or dates. Tournament results must never affect its own predictions. This is a conservative approximate availability rule, not independently verified result publication time.

## Input and provenance
- `run_tml_elo_experiment(paths: Sequence[Path], *, test_years: tuple[int,...]=(2023,2024,2025), embargo_days: int=28) -> dict`.
- Each `YYYY.csv` or `YYYY-<sha256>.csv` is a **local** original TML season export, strict 50-column header and CSV decoding. Verify each original byte SHA; immutable filename must match bytes. Reject duplicate season numbers, missing years, future source seasons, duplicate `(tourney_id,match_num)` across all files, invalid UTC-like or malformed tournament dates and IDs.
- A season can contain tournaments beginning on or after Dec 25 in the **preceding calendar year** (e.g. season 2025 began Dec 29, 2024). Group/release matches by actual `tourney_date`, rather than nominal CSV season. This affects chronological fold assignment.
- Include original `tourney_level` 250,500,M,G; hold TML `A` out separately due ambiguous official-tier semantics, exclude D/O/F. Record exclusions as counts, not silent drops.
- Exclude completed outcomes with RET, W/O, DEF, ABN, unfinished, missing player ID or same player ID. No future values (current match age, ranking, stats, score) enter Elo features. Two players are oriented **independently of winner**, alphabetically by stable ID, so a model is not trivially scored on winner-first CSV ordering.
- Reject dataset when fewer than three fully represented nonempty holdout calendar years, when any source file year duplicates, or if no preholdout warmup history exists. Source reports include SHA, byte size, row count, actual event filtering.

## Elo methodology and temporality
- Use **prior 1500** for all players, (K=24), base 10, scale 400. No holdout hyperparameter tuning.
- Predicted p(Player A) = `1 / (1 + 10**((ratingB-ratingA)/400))`, bounded for log loss at `1e-12`. Player A = stable ascending player ID, not CSV winner column.
- Surface Elo stores separate ratings and counts for hard/clay/grass. Adjust overall rating by `0.35 * (surface_rating - 1500) * n / (n + 20)`; 20 prior equivalent matches shrink sparse histories. No use of surface feature if not from the tournament's known pre-start surface.
- At each event start, retire pending finished tournament events whose *start* was at least 28 days earlier. Compute ALL eventual matchup probabilities from the same pre-event state; no match from that event updates Elo until embargo expires. Update a matured event as one **batch** using its pre-update ratings, not round ordering. Treat another event starting on the same date as equally unable to see its result.
- Group events by `(tourney_id, start_date)`, and fail if one source ID refers to different date/surface; never match on player names alone.
- Outcome label (y_A=1) iff winner is stable player A; ensure nontrivial 0/1 labels with a fixture containing both orientations.
- Fold classification uses the **actual tournament start calendar year**, not nominal season file. Use 2023, 2024, 2025 as fully disjoint holdout years, with all prior-year results only at the specified embargo time. A rating may sequentially update from earlier *test* events after embargo as a true prequential online evaluation; do not refit K/thresholds from holdouts.

## Scoring and output
- Per holdout year + aggregate n, Brier, log-loss for `coinflip`, `global_elo`, `surface_elo`; comparative differences (lower is better). Bootstrap *whole event clusters* with fixed seed, descriptive CIs if cluster support adequate. Report eligible/retired/skipped row counts and source SHA inventory.
- Output `HISTORICAL_SKILL_RESEARCH_ONLY`, `source_rights_scope=PERSONAL_NONCOMMERCIAL_RESEARCH`, `source_result_availability_exact=false`, `participant_known_at_event_start=false`, `t60_quote_verified=false`, `market_edge_verified=false`, `model_validation_trusted=false`, `allocation_enabled=false`, `stake=0`. This is not a deployable exact prematch prediction or strategy.
- A positive score improvement over 0.5 **is not** better than professional bookmaker no-vig implied probabilities, and never proves positive ROI. Best models may fail to beat coinflip; publish any negative result.
- No raw match rows or player names/IDs in persisted JSON reports. Use local filenames and content SHA provenance only.

## Tests and review
TDD assertions for chronological two-event embargo, same-tournament freeze, outcome-independent A/B orientation, calendar-year 2025 cross-year start, reproducible scores, deterministic cluster bootstraps, excluded retirements, duplicated event/match IDs, missing holdout years, hash mismatch, malformed source and file overwrite. Four-job Windows/Ubuntu Python 3.11/3.12 CI. No auto-merge into `main`.
