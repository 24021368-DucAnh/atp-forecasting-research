# Input Contract & Quality Audit — ATP V0.1 (2026-11-23)

## Goal and key invariant

**Unit of prediction:** one official ATP men's main-draw singles match, uniquely identified, with a confirmed start timestamp. Decision time is at least 60 minutes before the match start. No outcome knowledge or post-decision price may enter an eligible paper signal.

**Eligible competitions:** Grand Slam men’s singles main draw (BO5), Masters 1000 men’s singles main draw (BO3), ATP 500 men’s singles main draw (BO3). Exclude doubles, qualifying, ATP250, WTA, Challenger, exhibition, team competitions, futures and games already in progress.

## Data prerequisites

| Input source | Required minimum fields | Risk / fail-closed rule |
|---|---|---|
| Fixture | match/event IDs, both unique player IDs, tournament tier, round, surface, best-of, confirmed full start timestamp, source published/observed time | Reject TBA start, duplicate match, mismatched format, status not scheduled/delayed, stale fixture |
| Odds | match ID and both player IDs in A/B order; same bookmaker and market; both decimal odds, quote ID, published/observed/retrieved at, retirement settlement rule | Reject future/older-than-30-min quote, unknown retirement rule, mismatched player order, implausible overround |
| Features | exact 18-field vector, player history counts, feature schema fingerprint, created and data-asof timestamps, missing/imputed indicators, source rights and match reconciliation flags | Reject fabricated rank/rest, missing serve/return profile, future or uncertain time, opposing surface flags, schema drift |
| Model | immutable model id, train/calibration/validation windows, report id+SHA256, score time, calibrated probability + lower/upper uncertainty, sample sizes | Reject future model, stale prediction, untrusted report, failed calibration, no verifiable market edge, test leakage |
| Risk ledger | month (Asia/Bangkok), free cash, unsettled risk, protected funds, phase, daily count, gross realized losses, already selected IDs | Reject duplicate selection, monthly floor, weekly/annual cap, unsettled exposure, profit-lock pending |

### Critical temporal fields

`scheduled_start` and `as_of` are timezone-aware instants. `quote.observed_at` and `quote.published_at` must be <= `as_of` and `as_of - observed_at <= 30m`. `model.predicted_at <= as_of`, model age <=30m, and the model must have been released before scoring. `features.built_at <= model.predicted_at`; all underlying features must be known on or before the decision instant.

The historical `tourney_date` in Sackmann-style datasets is **usually a tournament-start date**, not a confirmed exact match-start time. Even tennis-data's daily `Date` is insufficient to certify a true T−60 quote. Closing odds must not be treated as executable T−60 odds.

### The 18 features in selected upstream ML model

In exact order:

`elo_diff`, `ov_diff`, `p_elo`, `form_p1`, `form_p2`, `h2h`, `rest_p1`, `rest_p2`, `rank_diff`, `min_nm`, `surface_clay`, `surface_grass`, `tour_wta`, `spw_diff`, `rpw_diff`, `ace_diff`, `bps_diff`, `sos_diff`.

1. Every rolling feature must be computed strictly *before* the current match's final outcome becomes known.
2. Player A/B identity must match the model's row orientation and odds quote order.
3. Rank differences cannot be silently set to zero for missing data; `imputed_fields` must disclose imputation and the strict gate rejects it.
4. `feature_schema_hash` is a SHA-256 fingerprint of the ordered names, not evidence that values are accurate. Upstream training data must be reconciled with live feature semantics.
5. Actual values of serve/return statistics must have historical source timestamps and account for opponents and sample sizes; `critical_missing` blocks unsupported contexts.

### Input data tiers

- **Live/forward eligible:** independently recorded fixture, valid odds observed at as-of, provenance, point-in-time features, independently validated model and risk state.
- **Historical-research-only:** matches and opening/closing prices with daily dates but no event-time quote snapshots.
- **Quarantined:** ambiguous IDs, duplicates, missing/contradictory timestamps, unsupported tournament/settlement, source conflicts, unverifiable licensing.

## Upstream code audit (inspected using GitHub connector)

Selected MIT-licensed ML repository: https://github.com/coenensam/tennis-match-predictor at commit `f548d978e09b3ef1a0783a1d315ec1fce1b6f70f`.

| Finding | Evidence in upstream | Required change |
|---|---|---|
| HIGH: approximate match dates | `src/tennis_predictor/data.py` computes `match_date = tourney_date + round_ord*1.3 days` | Fetch genuine match start/end times; don't certify day-level fatigue as exact |
| HIGH: fuzzy join risks matching wrong event | `src/tennis_predictor/config.py` sets `clv_max_date_gap=16` days; `clv.py` matches approximate names and nearest dates | Strong IDs + verified one-to-one mapping with competition and time |
| HIGH: training/inference skew | `features.py` trains `rank_diff` on observed ranks, `predict.py` sets `rank_diff: 0` | Populate genuine as-of ranking or mark unavailable and abstain |
| HIGH: native downloader fragile | `data.py` downloads from JeffSackmann raw GitHub paths; historical repositories changed availability during 2026 | Adapter with independently validated source and source-use terms |
| HIGH: not a T−60 executable backtest | `clv.py` evaluates Pinnacle closing odds, not price snapshots known one hour before a match | Keep CLV as a quality benchmark; separately run forward quote snapshots |
| MEDIUM: winner/loser orientation risk | Historical train rows randomized but legacy odds CSV names winner and loser | Enforce A/B IDs and snapshot-time identity; no outcome-based selection |

These are method and integration findings, **not** a claim that the upstream project's published results are false. The repo remains useful for Elo/XGBoost baselines, but it needs the corrected input adapter before running the project's strict selection policy.

## Selection and risk policy

`p_A_lower` is the conservative, separately validated probability lower estimate for player A. The lower probability for B is `1 - p_A_upper`. For each side, calculate:

`EV_lower = p_lower * odds - 1`.

Only if `EV_lower > 0.02` and all gates pass, compute `Kelly = max(0, EV_lower/(odds-1))` and `Stake = 0.25*Kelly*min(free_cash, X)`, capped by max 1% X, open exposure, monthly free-cash floor, remaining weekly/annual loss budgets and (if after lock) 20% of unlocked residual. The condition `EV_lower>0.02` is an **untested policy hypothesis**. An interval generated using in-sample predictions is not acceptable.

**Profit lock:** when no open position and normal wallet >=1,050, transfer 1,040 to protected cash, leave residual active. Never reinvest protected principal. On rollover, `net = protected + remaining unlocked - 1,000`; deficit must appear as external replenishment, NOT be silently erased.

This input gate has no online betting connection. Real-world bookmaker retirement/void rules may differ and are not automatically inferred.

## Evaluation that is still REQUIRED

1. Verified source contracts and data licensing.
2. Chronological train/validation/calibration/untouched test splits with no pre/post-match leakage; use an independent calibration period. `TimeSeriesSplit` alone does not solve available-at-time joins or overlapping event/feature windows.
3. Compare to market de-vig + Elo with Brier/log loss/calibration and empirical selection ROI (confidence intervals). No self-certified edge reports.
4. Test top-2/5/10 allocation with **equal total stakes** in a historical diagnostic; for live stop-loss/profit-lock policies report both allocated capital and actually staked turnover separately.
5. Multi-season, by-market, by-surface risk sensitivity, walkover/retirement-specific settlement and forward paper logs.

**Readiness:** Ready for offline schema and accounting tests; NOT ready for live prediction or any money deployment.
