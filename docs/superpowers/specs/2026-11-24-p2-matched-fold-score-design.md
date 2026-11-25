# P2A — Chronological Matched-Fold Forecast Scoring Design (2026-11-24)

**Issue:** #12. **Stage:** evaluation-only helper, no actual trained model/certification.

## Why
The existing `research_train.py` performs a single chronological 60/20/20 split, while P2 requires at least 3 separate future holdouts, paired comparisons and visible uncertainty. Training must wait for P1 source-rights and main-draw completeness. However, a deterministic *scorer* can be implemented and tested now on synthetic, untrusted forecast rows; it must never report trusted market edge.

## Approaches
1. Tune XGB on historical closing odds and count ROI as tradable: reject, this uses unavailable T−60 prices and market leakage.
2. Rewrite the ML training system before source repair: high risk of wasted work and feature leakage; defer until source approved.
3. **Selected:** build a small strict offline fold scorer for independently generated/out-of-time probabilities (market no-vig, Elo, calibrated XGB). Require matched rows and chronology; report Brier, logloss, per-fold counts and cluster-resampled paired delta confidence intervals. No automatic trusted model report.

## Input
At least three chronological disjoint fold records, each with literal `train_end`, `calibrate_start`, `calibrate_end`, `test_start`, `test_end` ISO dates, and `rows`. Rows have `match_id`, `event_id` (stable tournament edition ID), `date`, `outcome_a` (0/1 int), `p_market`, `p_elo`, `p_xgb` (strict probabilities between zero and one), `tier`, `surface`. A model name suggests origin, not proof. Dates must obey `train_end < calibrate_start <= calibrate_end < test_start <= test_end`; all holdout dates must lie in the window; every match ID appears exactly once; adjacent folds have non-overlapping test dates and training may expand.
Within each fold, every model and no-vig market is scored on **exactly identical records**. Missing probabilities or outcome → reject rather than quietly change sample size. Match IDs cannot repeat. Market row values are historical probability snapshots of unknown quote time, **not** executable offers; no stake/ROI or CLV from this component.

## Output
Per fold and aggregate log loss/Brier for market, Elo and XGB, count, paired delta log loss (`xgb_minus_market` and `elo_minus_market`), paired cluster bootstrap 95% CI, source-independent deterministic seed and replicate count. Cluster by `event_id` **across fold context** (fold ID, event ID), resample clusters within folds and preserve event dependence. Small effective cluster count yields `insufficient_cluster_support`, not a confidence claim. Coverage is 100% of submitted paired rows, not of all calendar matches.

`status=UNTRUSTED_FORECAST_EVALUATION_ONLY`, `mode=HISTORICAL_RESEARCH_ONLY`, `market_edge_verified=false`, `validation_report_trusted=false`, `eligible_for_model_training=0`, `allocation_enabled=false`, `stake=0`. A lower XGB loss is NOT a proof of market betting edge.

## Non-goals
No model fit, new features, data ingestion, real odds, source-rights acceptance, inferred outcomes, betting execution, or trusted signed release report.

## Acceptance
TDD synthetic 3-fold positive/negative, date overlap, same-day leakage, duplicate IDs, missing odds, nonbinary outcomes, contradictory probabilities, cluster CI reproducibility; 4/4 Actions green. Do not merge before independent review.
