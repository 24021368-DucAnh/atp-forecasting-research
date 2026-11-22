# ATP Historical Research Pipeline — V0.2 design

## Goal
Extend the already verified fail-closed ATP Input Gate with a reproducible **offline ATP research pipeline**: ingest historical match/odds files; replay pre-match Elo by date without same-day outcome leakage; train an optional XGBoost model; calibrate on a disjoint chronological block; compare untouched held-out predictions with Elo and no-vig market odds.

## Approaches
1. Run the upstream pipeline unchanged: rejected; its default Jeff Sackmann data URL is currently unavailable and it uses an approximated tournament date, while its live inference fills rank_diff with 0.
2. Use only bookmaker odds to pick matches: rejected; no independent prediction evidence.
3. **Selected:** retain upstream-compatible 18-feature vector, reuse the MIT-licensed upstream's surface-Elo formulas with attribution, and build a separately audited tennis-data-style historical adapter. Historical date-only odds are *research comparison only*, never live tradable T−60 prices.

## Limits
- Python >=3.11, Windows PowerShell 5.1, optional `.[ml,test]` dependencies.
- Scope ATP singles; training may use ATP250 background history; held-out evaluation on Grand Slam/Masters1000/ATP500, if sufficient sample; no guarantee of profitability.
- Historical odds (`B365W/B365L`) are attached to winner/loser after results: remap to canonical player A/B before model evaluation; never train on outcome labels, odds as features, score, final serve stats, or a winner-first player orientation.
- Group by actual **date** (not time) and update all player histories only **after** capturing pre-date features; rows of one day are predicted from prior completed days. No true intra-day timestamp means T−60 cannot be certified.
- Use deterministic names for research-only pairing; names are not stable identity and do not authorize live-gate input.
- Sequential train/calibration/test grouped by date, no random split; report sample counts, missingness and skip reasons; keep unvalidated evidence untrusted; no automatically trusted registry.
- Do not bundle third-party historical CSV files, respect third-party data license.

## Outputs
`research-audit CSV`: counts, coverage, collisions, excluded matches, date-only limitation.
`research-train CSV --out REPORT`: JSON with data/split/model/market metrics, warnings, and explicit `live_eligible=false`, `allocation_enabled=false`.

## Guardrails
- Fail on malformed source columns or too little chronological coverage; skip and account for invalid rows; do not guess unknown tournament formats.
- Test time leakage, winner-first label leakage, no-vig orientation, independent calibration split, lack of odds, and untrusted reports.
- Keep V0.1 gate and its tests unchanged; no sportsbook networking, no real money.
