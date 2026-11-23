# P1.2 Source Identity & Provider Schema — Design (2026-11-23)

## Decision
Implement an **independent read-only Valuebetennis CSV inspection adapter**, not direct ingestion into `HistoricalMatch`, XGBoost or the live Input Gate.

**Why:** Valuebetennis publishes a CC BY 4.0 dataset with stable-looking player/match IDs and UTC timestamps. However its `categorie` broad `Main tour` is insufficient to distinguish ATP250/ATP500; `tour` is a numeric round 0–12, not ATP tour, and does not by itself certify main-draw membership. Its Pinnacle odds are opening/closing prices with no verified T−60 snapshot. Forcing the source into the Tennis-Data schema now would invent information.

Provider: https://www.valuebetennis.com/en/donnees.htm (CC BY 4.0 according to provider; keep attribution). The provider states annual semicolon-delimited CSV, regenerated regularly; files include both ATP and WTA plus lower circuits. The raw dataset has **not yet been verified by running this adapter against provider downloads**, so green CI with synthetic fixtures is not full data acceptance.

## Outputs
New command:
```
python -m atp_gate valuebetennis-profile [--start-year YYYY --end-year YYYY] FILE.csv ...
```
Only reads local input files (never downloads or writes raw data). Prints JSON inventory:
- `mode=HISTORICAL_RESEARCH_ONLY`, `profile_version=P1_VALUEBETENNIS_1`
- Source byte-size, SHA-256, original file basename; no credentials or personal paths in report
- Total rows, invalid row counters, ATP/WTA exclusion, ITF/Challenger exclusion, duplicate match IDs
- Observed years and expected missing years; `categorie` raw distribution; observed surfaces, dates; record counts by year
- Stable player-ID string count, ID -> multiple display-name alias count, ambiguous display name -> multiple IDs count (diagnostics, not identity authorization)
- Missing opening/closing odds counts, without changing accepted record count
- `tier_mapping_verified=false`, `main_draw_verified=false`, `t60_quote_verified=false`, `source_file_origin_verified=false`, `eligible_for_model_training=0`, `stake=0`, `allocation_enabled=false`.
- `status=INSPECTED_UNMAPPED` for valid observed ATP Main tour/Masters/Grand Slam entries, or `INCOMPLETE` if expected years or valid observations are absent.

## Input invariants
- Strict semicolon CSV with UTF-8 BOM support; required columns: match_id, date, tournoi, tournoi_id, categorie, genre, surface, tour, joueur1, joueur1_id, joueur2, joueur2_id, vainqueur_id, cote1_ouverture, cote2_ouverture, cote1_cloture, cote2_cloture.
- Identifiers are nonempty positive integer *strings*, not floating-point names. No same-player self matches. Winner ID must match one of two player IDs.
- Date parsed as UTC per provider contract, allowing ISO-8601 UTC Z/+00 and provider-naive format `YYYY-MM-DD HH:MM:SS` (explicitly tagged `PROVIDER_DECLARED_UTC_NOT_VERIFIED_ACTUAL_START`). Bad/missing timestamps are rejected.
- `tour` is a numeric round between 0 and 12. It is NEVER used as ATP/WTA designation or as proof of main draw. Do not guess cutoff.
- `genre` = `atp` to include; WTA and unknown are excluded, never silently included.
- Categories `Main tour`, `Masters`, `Grand Slam` are provisionally `TOUR_CANDIDATE`, **not** actual verified ATP250/500/1000/Slam. ITF/Challenger excluded.
- Missing odds recorded but not used to impute, infer, train or backtest.
- Identical match ID repeated across sources is deduplicated/flagged; no accidental duplicate match features.
- If one source filename appears in multiple paths, reject (provenance collision). Both year bounds required or neither.

## Rejected alternatives
- Assign all Main tour entries to ATP500 — invalid, contaminates target tiers.
- Assume category "Masters" proves ATP Masters 1000 and main draw — unverified.
- Use opening or closing odds as T−60 — false, no timestamped quote.
- Combine Valuebetennis directly with Tennis-Data by name — risks alias collisions and leakage.
- Download provider files automatically into the repo — unstable snapshot and undesired bulk data movement.

## Acceptance
- Red-green pytest demonstrates missing module then test failures for bad ID/round/date and WTA exclusion.
- 4 GitHub CI jobs pass on Windows/Ubuntu, Python 3.11/3.12.
- No change to training, model report, risk gate or live eligibility.
- Provider actual-data sampling is a **separate acceptance gate**: if not run, mark P1.2 provider-adapter integration partial, not complete.
