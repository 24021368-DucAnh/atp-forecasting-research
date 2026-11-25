# P1.4d — TennisMyLife February 2024 Research Candidate Audit

**Context:** User explicitly restricts this ATP project to personal/noncommercial ML research. TML's own README and database page permit personal, educational, noncommercial use, but forbid raw CSV redistribution without permission; preserve attribution and data-origin provenance. Source: https://github.com/Tennismylife/TML-Database and https://stats.tennismylife.org/tennis-match-database.

**Preflight observation (GitHub 2024.csv on 2026-11-24):** 3,076 rows × 50 columns, 455 rows whose tournament *start date* is February 2024 including Davis Cup, and 340 singles main-tour rows corresponding to 12 official events (eight ATP 250, four ATP 500); none of those rows provides actual individual match date or timestamp. The GitHub file is historical reference, not the canonical frequently updated source. Source Git blob: `cf513429259b4a15e84e2021206895d9bd4ff772`. We must check local file hash; a Git blob SHA is not raw SHA-256.

## Alternatives and selected approach
1. Continue treating February 2024 as absent: wrong for noncommercial research when a separate public historical source exists.
2. Silently splice new source rows into Valuebetennis training set: destroys provider provenance, possibly duplicates winner/loser rows, conflates tournament start with match date; rejected.
3. **Selected:** add a separate TML candidate-source audit, with source-specific tournament-ID crosswalk linked to the pinned official ATP event registry and fail-closed reporting. It does not replace the Valuebetennis CSV or certify real T−60 odds.

## Interfaces
- `src/atp_gate/tml_historical_audit.py`: `audit_tml_february_2024(csv_path: Path, crosswalk: dict, official_calendar: dict) -> dict`.
- `docs/registries/tml_2024_feb_source_crosswalk_v1.json`: twelve curated events, TML IDs, source tournament start dates, names, surface, official tiers, observed row/round counts.
- New CLI `python -m atp_gate tml-february-audit path/to/2024.csv docs/registries/tml_2024_feb_source_crosswalk_v1.json docs/registries/atp_2024_february_official_events_v1.json --out reports/tml_2024_feb_audit.json` only reads local CSV and registries; writes ignored JSON if out is not an input.
- No downloader in this PR. User can use provider's published `/api/data-files` endpoint for opt-in manual downloads. Scheduling and re-download policy are a separate, explicitly configured phase.

## Contract
- Require known 50-column TML schema; the source is comma-delimited UTF-8-SIG.
- Streaming SHA256 and size. Record source filename, license URL, local observations and counts. No raw CSV bytes in repo.
- Validate official event crosswalk: each official key exactly once and matches pinned official calendar with the same tier/start date; per-event TML tournament ID unique.
- Audit selected TML tournament IDs against round histogram, exact season start dates, surface, player IDs, winner/loser distinctness, duplicate `tourney_id + match_num`, score (blank/retirement/WO flagged) and `best_of=3` for these events. Distinguish critical errors from audit warnings. Do not assume unique `match_num` globally.
- Report provider-level discrepancies: TML source-level `A` for Doha/Los Cabos despite official ATP250; crosswalk official tier controls; never trust TML `A` as Masters status.
- Return status `SOURCE_CANDIDATE_REVIEW_REQUIRED` even when source-shape/rounds agree, because independent official draw and match outcomes are unverified. If discrepancies exist, status `SOURCE_CANDIDATE_INCONSISTENT` with errors and counted affected events. Always `eligible_for_model_training=0`, `main_draw_verified=false`, `t60_quote_verified=false`, `allocation_enabled=false`, `stake=0`.
- `tourney_date` equals tournament-week/start date, not individual match date, and MUST NOT enter time-ordered row-level leakage-free training as if first-serve time.
- Research licensing is noncommercial; explicitly avoid redistribution, market execution, commercial or public betting service.

## Acceptance tests
Synthetic CSV reproduces 12 events/340 matches and checks exact grouping, duplicate-match, missing player, wrong start date/tier, unexpected round cardinality, missing source file, output overwrite, schema change and no-training gate. Also require a verified local original 2024 source inspection report matching the observed provider snapshot (record differences if later corrections exist).

**Non-goals:** official outcome proof, bookmaker odds collection, validated model or live trading.
