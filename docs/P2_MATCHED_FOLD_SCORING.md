# P2A — Matched Chronological ATP Probability Scoring (Research Only)

This component supports **comparisons of submitted out-of-time predictions**, not model training, official draw certification or a real-market betting strategy.

## Why it exists
The prior single 60/20/20 research split provides no evidence of multi-season persistent market advantage. Issue #12 requires **at least three chronological holdout folds**, identical match sets for Elo/XGB/market comparisons, and uncertainty that respects tournament-level clustering. Implementing this pure scorer first helps us test evaluation design without using 2024 February missing or unlicensed outcomes.

## Python API

```python
from atp_gate.fold_scoring import audit_fold_scores

report = audit_fold_scores(
    folds, bootstrap_replicates=400, seed=20261124,
)
```

`folds` is a **list of at least 3 dictionaries**. Each fold must specify exactly `train_end`, `calibrate_start`, `calibrate_end`, `test_start`, `test_end`, and `rows`. All dates use `YYYY-MM-DD`, with train earlier than calibration earlier than test. Test windows must be disjoint and in increasing chronological order; training cutoff must increase across folds.

Each `rows` entry must contain exactly:
- `match_id` and `event_id`: stable, nonempty match/tournament-edition identifiers; duplicates across folds are refused.
- `date`: actual test match date inside that fold's holdout window.
- `outcome_a`: integer 0 or 1, verified winner orientation **assumed**, not independently established by this tool.
- `p_market`, `p_elo`, `p_xgb`: strict (0,1) probabilities for the **same** player A and match. No missing model or market probability is allowed.
- `tier`: `ATP_500`, `MASTERS_1000`, or `GRAND_SLAM`.
- `surface`: `HARD`, `CLAY` or `GRASS`.

`p_market` should be a *historical two-sided de-vig comparator* when that data is available. Neither an opening nor a closing probability is certified to have existed at T−60. This module never claims that any price was executable.

## Math
- Brier score = mean((p-y)^2), lower better.
- Log loss = negative mean([y\log p+(1-y)\log(1-p)]), lower better.
- Difference `xgb_minus_market_log_loss` = XGB log loss minus matched market log loss; **negative** means the submitted XGB predictions have lower loss on that submitted sample, *not* that the model beats available sportsbook prices.
- Paired event-cluster bootstrap: within each fold resample complete event groups with replacement, then recompute aggregate loss difference; 95% percentile intervals are **descriptive**. This does not correct for feature contamination, data-snooping, year/season drift, unavailable quotes or provider selection.
- When there are under 6 distinct event clusters total or fewer than 2 groups in any fold, returns `INSUFFICIENT_CLUSTER_SUPPORT` and no confidence interval. Even with more clusters, nominal intervals do not establish a reliable trading edge.

## Output is always fail-closed

```json
{
  "status": "UNTRUSTED_FORECAST_EVALUATION_ONLY",
  "mode": "HISTORICAL_RESEARCH_ONLY",
  "source_rights_verified": false,
  "asof_feature_provenance_verified": false,
  "t60_quote_verified": false,
  "market_edge_verified": false,
  "validation_report_trusted": false,
  "eligible_for_model_training": 0,
  "allocation_enabled": false,
  "stake": 0
}
```

No code in this module signs or registers a model, selects bookmaker odds, simulates trade placement, computes ROI or releases money.

## Pending work and acceptance gates
1. P1.4d #17: verified licensed historical match-level results + complete official main draws + stable player identity, especially 12 missing February 2024 tournament editions.
2. P2 #12: run independently generated genuine past-only forecasts over 3+ multi-season folds; enforce point-in-time data availability and reproduce source hashes, model versions, exact fold prediction files. **This scoring helper does not produce those forecasts.**
3. P3 #13: separately document offer quote source and **observed** T−60 timestamp plus settlement rules; only then may **paper-only** ROI, CLV and stress simulation be interpreted as a diagnostic.
4. Always compare all baselines on identical match IDs; avoid tuning final test thresholds after reading holdout outcomes. Publish negative comparisons.

**Related:** [Source intake Draft PR #23](https://github.com/24021368-DucAnh/atp-forecasting-research/pull/23), [P2 Issue #12](https://github.com/24021368-DucAnh/atp-forecasting-research/issues/12).
