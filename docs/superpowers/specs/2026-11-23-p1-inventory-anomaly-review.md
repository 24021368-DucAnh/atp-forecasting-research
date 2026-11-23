# P1.3b — Fail-closed tournament-inventory anomaly review (2026-11-23)

## Input evidence / problem statement
The uploaded real 2022–2026 Valuebetennis tournament inventory (JSON SHA-256 `eccb403bb6c0874e30f4e304c7be23678d2d1e6db095fd9174ee1753a225665b`) reconciles **323 UTC-calendar-year groups** and **19,065 provisional ATP matches** with zero missing tournament IDs and no same-key metadata conflicts. Yet this does NOT imply correct edition identity, full round coverage or intended tournament scope.

Observed:
- Nine provider `tournoi_id` values appear across Dec/Jan boundaries, splitting an event into two UTC-year groups. These are candidates for the same event edition, but should not be automatically merged without an official edition identifier.
- Australian Open 2024 (ID 12440) has 236 rows, last 2024-01-23 and no round code 10/12; official men's final was on 2024-01-28.
- Indian Wells 2024 (ID 12589) has 47 rows, vs 2023 131; source appears to omit early rounds.
- Shanghai 2024 (ID 13649) lacks code 12 and Rome 2026 contains only 49 candidate rows, missing later stages.
- For 2024, there is a 61-day interval between first observed event starts 2024-01-08 and 2024-03-09; no event begins during February. The inventory's existing `observed_years` check does not ensure event-level completeness.
- Special-format event names (ATP Cup, United Cup, Laver Cup, Olympics, Next Gen ATP Finals, Nitto ATP Finals) account for at least 416 candidate records across 23 UTC-year groups. A provider `Masters` label includes the Nitto ATP Finals, which is **not** ATP Masters 1000.

Official checks: https://ausopen.com/articles/news/sinner-winner-italian-takes-first-major-ao-2024 ; https://www.atptour.com/en/scores/results-archive?year=2024 ; https://www.atptour.com/en/news/2026-atp-tour-calendar-announced .

## Design
Standalone **read-only** function `review_tournament_inventory(report: dict) -> dict`, operating on the saved report from P1.3a. It must not re-open raw CSV files, change an original report, guess ATP tiers/round qualifiers or train a model. Output:
- `status=REVIEW_REQUIRED`, `mode=HISTORICAL_RESEARCH_ONLY`, `review_version=P1_INVENTORY_REVIEW_1`
- integrity checks: accepted count = inventoried count = sum event counts; per-event sum raw `round_counts` = event candidate matches; uniqueness of `(UTC year, ID)` keys; by-year group/match totals match parent report
- `cross_year_tournament_ids`: every provider ID spanning calendar years, including year/group/match details, but **not** a canonical edition merge
- `special_format_candidates`: exact named-prefix flags for `ATP Cup -`, `United Cup -`, `Laver Cup -`, `Next Gen ATP Finals -`, `Nitto ATP Finals -`, `Olympics -`, preserving original provider labels; count groups/rows and label them review candidates, not an exhaustive rule
- `missing_final_code_candidates`: Grand Slam or source `Masters` groups **except explicitly special-format events** missing raw code 12; avoid claiming which original match is missing until official bracket comparison
- `large_event_start_gaps`: consecutive group start dates in the **same UTC year**, both starts Jan–Oct, >45 days. Label only a coverage warning, not definitive proof of missing tournament.
- hard gate flags `tier_mapping_verified=false`, `main_draw_verified=false`, `eligible_for_model_training=0`, `allocation_enabled=false`, `stake=0`.
- input invalid/reconciliation mismatch -> raise ValueError, CLI `status=ERROR`, nonzero.

New CLI `python -m atp_gate valuebetennis-review INPUT.json [--out reports/valuebetennis_review.json]` validates and prints a compact JSON summary (counts and top entries) while optionally persisting full review locally. If output not supplied, it remains read-only.

## Alternatives rejected
1. Mutate `source_profile` or current provider inventory to magically set `COMPLETE` based on 5 years: unjustified.
2. Merge cross-year records on UTC-year alone or infer a target-year from dates: risks misclassifying edition. Report only.
3. Guess `Main tour=ATP500` or `Masters=Masters1000`: evidence shows wrong for Finals and ATP 250.
4. Universal round threshold for all event types: main draw remains externally unverified.
5. Commit raw provider CSVs, 256kB research JSON or player-level records: unnecessary.

## Acceptance
Test-first red/green for 2024-style missing rounds, cross-year IDs, out-of-scope name flags, count mismatch fail-closed and normal no-anomaly case. Existing 125 tests plus new tests pass on all four Windows/Linux Python 3.11/3.12 CI variants. User still must independently verify ATP event tiers, exact draw coverage and market quote timestamps; no market edge claimed.
