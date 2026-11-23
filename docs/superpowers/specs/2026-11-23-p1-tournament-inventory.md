# P1.3a — Tournament-season/round inventory design (2026-11-23)

## Intent
Construct a **read-only, source-grounded** tournament inventory from Valuebetennis accepted ATP candidates to support later verification of ATP 250 vs ATP 500 and main-draw eligibility. No prediction/training eligibility can be conferred.

## Baseline
PR #6 merged. User ran 2022–2026 provider annual CSVs on Windows: 414,878 rows, 19,065 ATP provisional candidates, 944 player IDs, 0 candidate duplicate match IDs, observed year counts 4,060 / 4,089 / 3,409 / 3,918 / 3,589. Provider's 2026-11-22 French open-data listing publishes an aggregate 414,878 rows for the same five seasons. Exact provider-hosted file hashes remain unverified.

Existing `inspect_valuebetennis_sources` has a single accepted-row pass and original source SHA-256 manifest; it exposes only year/category/surface totals. It **cannot show the per-event round distribution** or which `Main tour` entries need official tier verification.

## Design decision
Extend `inspect_valuebetennis_sources(paths, *, expected_start_year=None, expected_end_year=None, include_tournaments=False)` with opt-in per-event aggregation performed **inside the existing validated accepted-row loop**. Do NOT duplicate the eligibility parser. Existing callers and default report schema stay unchanged.

When enabled, include:
- `tournament_inventory`: `tournament_seasons` sorted by `(match_utc_year, tournoi_id)`, with raw tournament ID, sorted raw names/categories/surfaces, rounds as numeric-code counts, first/last observed UTC times, source filenames and candidate match count.
- `tournament_inventory.summary`: number of tournament-season keys, total inventoried candidate rows, invalid tournament IDs/names, conflicting metadata count, by-year tournament key counts and total candidate rows from the existing inspector.
- `tier_mapping_verified=false`, `main_draw_verified=false`, `eligible_for_model_training=0`, `t60_quote_verified=false`, `allocation_enabled=false`, `stake=0` (inherited).
- A same-season `tournoi_id` that appears with conflicting display names or raw category labels is marked `metadata_conflict=true`. Do not resolve by majority.
- Invalid tournament ID or missing tournament name is counted as `missing_tournament_metadata` and not placed in inventory, while `atp_candidate_matches` keeps its original value. This does not retroactively alter user-verified 19,065 candidates.

New CLI command `valuebetennis-tournaments --out reports/valuebetennis_tournament_inventory.json [--start-year YYYY --end-year YYYY] PATH...` writes full JSON report **locally** and prints compact summary with explicit `INVENTORIED_UNMAPPED` status if full expected year coverage, at least one inventoried record, and zero missing tournament metadata. `INCOMPLETE` status + exit code 2 for missing required years, missing tournament metadata, no accepted rows, or no inventoriable tournament keys. Invalid schema returns an `ERROR` without creating a false success report. Full saved report remains only in ignored `reports/`.

## Invariants
- All match counts in inventory derive from same accepted ATP candidate list as the existing source inspector, excluding WTA, Challengers/ITF, invalid/winner/round/date and repeated match IDs.
- A tournament season is keyed by UTC year and positive numeric `tournoi_id`. This is a **provider UTC-year grouping**, not an independently verified official ATP tournament season.
- `round_counts` are raw `tour` integers (0–12) with no global qualifying/main-draw threshold.
- `categorie=Main tour` remains unmapped. Source attribution CC BY 4.0; source-file origin and T−60 price unverified.
- Do not commit provider CSV bytes. Do not mutate the historic name-keyed research model or risk gate.
- A data-only `INVENTORIED_UNMAPPED` result is **not** a signed authoritative tournament-tier registry.

## Acceptance criteria
1. Test-first red/green verifies two years sharing one tournament ID produce separate records, that raw round counts match accepted rows, and duplicate match IDs aren't double counted.
2. Conflicting name/category metadata is flagged, not guessed; missing/invalid ID is counted and fails command readiness.
3. CLI writes local JSON with source SHA-256 and emits compact warning-laden summary; incomplete years exit 2.
4. Entire GitHub CI matrix passes (Windows/Ubuntu, Python 3.11/3.12); independent source-file verification and official tier mapping remain blockers in issue #7.
