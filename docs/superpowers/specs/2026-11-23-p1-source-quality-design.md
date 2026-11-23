# P1.1 — Multi-season Source Quality Profile (Design)

**Date:** 2026-11-23

## Intent
Before extending ATP research to several seasons, show exactly which **accepted historical observations** each file contributes, which years/tournament tiers/surfaces are represented, and where odds or rankings are missing. All outputs are historical research artifacts with zero live allocation.

## Current state
`load_historical_matches()` already checks the Tennis-Data-style input schema, completion status, tournament tier, date, duplicate match keys and source SHA-256. Existing `research-audit` reports global counters only. `research-train` does not independently verify source license or authoritative player IDs. The existing 2026 snapshot was accepted 984/1016 with 475 history-eligible matches and 121 target holdout observations. The 2026 report is repeatable in the user's Windows Python environment.

## Alternatives
1. **Modify the core loader and existing audit result**: one fewer module, but raises regression risk for training/manifest contracts.
2. **New read-only profile layered on the loader — selected**: preserve existing fit, reproducibility, and risk policy; add explicit per-source/year/tier/surface coverage and missingness.
3. **Import a new external provider immediately**: rejected for this iteration; Valuebetennis's public `categorie` only says `Main tour` without a safe, verified ATP250/ATP500 classification, and raw schema samples have not been independently inspected. Source taxonomy and rights belong to a separate adapter PR.

## Contract
Function `profile_historical_sources(paths, *, expected_start_year=None, expected_end_year=None) -> dict` returns:
- `status`: `PROFILED` for an inspectable accepted-data inventory or `INCOMPLETE` for missing requested years / no accepted matches.
- `source_audit`: the unchanged aggregate audit and SHA-256 source manifest.
- `coverage`: observed years, missing requested years, accepted matches by year, tier, surface, year-tier matrix, earliest/latest accepted date, unique player **name strings** (not verified identities), accepted counts per input filename.
- `quality`: missing-odds and missing-rank fractions/counts over accepted matches, plus coverage by year. Rejected rows use the original aggregate audit.
- `warnings`: empty or incomplete source, deduplicated observations, missing odds/ranks, unverified license, unverified player identity, day-only timing, unsupported T−60.
- `live_eligible: false`, `allocation_enabled: false`, `validation_report_trusted: false`, `stake: 0`.

The CLI `python -m atp_gate research-profile [--start-year YYYY --end-year YYYY] PATH [PATH ...]` must print JSON and return 0 for `PROFILED` and 2 for `INCOMPLETE` / invalid input. No writes to data, reports or model registry.

## Precise scope
- Reuse loader output instead of reimplementing eligibility. A duplicate across files is counted only once in accepted matches; duplicate count remains visible in the audit.
- Stop with explicit error on duplicate source basenames (even across different folders), because `source_row` and the saved report manifest use basenames.
- The expected range is **inclusive** and may be omitted; specifying only one endpoint is an error; no extrapolated full-season completeness guarantee.
- No URL downloading, automatic rights approval, odds timestamp inference, player-ID guessing, real-money API, or XGBoost changes.
- Synthetic tests must include a cross-year duplicate and missing year.

## Source-candidate provenance to review
- Valuebetennis open seasonal CSV: https://www.valuebetennis.com/en/donnees.htm ; site publishes CC BY 4.0 with attribution, ATP/WTA, player IDs, UTC match time, opening/closing Pinnacle prices. **Opening/closing quotes are not verified T−60 snapshots.** Its published `categorie` uses broader `Main tour` and cannot automatically distinguish ATP250 vs ATP500. Verify file structure and source rights before any data adapter.
- Tennis-Data: https://www.tennis-data.co.uk/data.php ; usage stated for private individuals, not commercial or training products using AI/bots. The existing externally mirrored historical snapshot is research-only and its mirror does not automatically confer rights.
- Jeff Sackmann mirrors have CC BY-NC-SA 4.0 restrictions; permission must be assessed for the intended use.

## Acceptance
- Existing 102 tests and new focused tests pass on Python 3.11/3.12 and Ubuntu/Windows CI.
- A 2026-only input with expected 2022–2026 is marked `INCOMPLETE`, not pretended complete.
- Only accepted records contribute to coverage/quality; the audit still reports rejected records.
- No data or report gets committed. The study remains paper-only.
