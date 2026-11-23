# P1.4b — Raw Valuebetennis source gap forensics (design)

Date 2026-11-23. Precondition: P1.4a passed on user Windows: `COVERAGE_REVIEW_REQUIRED`, 12/12 February 2024 events absent from the **accepted** inventory, including four ATP500. The original inventory is pinned by SHA-256 `eccb403bb6c0874e30f4e304c7be23678d2d1e6db095fd9174ee1753a225665b`.

## Goal and scope

Investigate **why** an official ATP event is missing from the accepted provider tournament inventory. Was the event absent from the local CSV altogether, present as WTA/Challenger, excluded by the existing data contract (invalid ID/winner/round/name), or simply named differently? Do **not** claim that an unmatched name/city proves the match was absent, or that a filter error has been corrected.

## Architecture (decision)

Create `src/atp_gate/source_gap_forensics.py`, a **read-only per-local-file report** that:
1. Calls existing P1.4a `audit_official_calendar_coverage` to verify the full inventory counts and the curated official event reference. Both must be pinned to the exact inventory-byte SHA.
2. Requires the local annual CSV basename, exact byte size and SHA-256 to match the matching `source_files[]` record in the pinned inventory. Any drift fails closed; source origin is *not* independently authenticated to provider hosting.
3. Scans that CSV with the documented semicolon CSV schema. Computes raw records by **explicit UTC calendar month** `YYYY-MM` regardless of ATP/WTA and then by genre and *original raw category* for ATP. Invalid date rows are counted separately as `undated_rows_outside_month_attribution` (cannot assign them to February).
4. Runs the same ordered ATP candidate validation and deduplication rules as P1.2 on the **whole file**, reconciling the full-file accepted count with `coverage.by_source[basename]`. Recognizes all selected rejection reasons (WTA, other circuit, excluded category, invalid identity/winner/round/date/name, duplicate).
5. For each official event in the provided curated calendar, compares the original `tournoi` string city suffix after `' - '` and the **raw row date** overlapping official event days +/- 4 days. This is an *event investigation hint* only, never a verified match/edition mapping; reports reasons by group and matched raw row counts in aggregate, never player IDs/individual rows.
6. Uses three diagnostic labels for each official event: `NO_MATCHING_RAW_CITY_DATE_ROWS` (no such rows in this one source file under strict matching), `ONLY_FILTERED_RAW_CANDIDATES` (rows exist but all fail acceptance), `ACCEPTED_SOURCE_CANDIDATE_PRESENT` (would be present in accepted pool; requires further event ID review). Never labels a source complete or fixes anything automatically.
7. Output `status=RAW_SOURCE_FORENSIC_REVIEW_REQUIRED`, `source_scope=ONE_LOCAL_CSV_ONLY`, original SHA and source manifest, month counts, reason counters, per-event summary, and strict flags `eligible_for_model_training=0`, `tier_mapping_verified=false`, `main_draw_verified=false`, `t60_quote_verified=false`, `allocation_enabled=false`, `stake=0`.

New CLI `python -m atp_gate valuebetennis-gap-forensics CSV INVENTORY OFFICIAL_CALENDAR --month 2024-02 [--out reports/...] `. CLI returns 0 if forensic analysis completed (regardless of gaps) or 2 on invalid source/hash/schema/malformed report. Never overwrite original CSV, inventory or official calendar. `--out` optional, full report remains ignored/local.

## Important limitations
- The diagnostic file scope covers one CSV, not all historic sources. The source may have malformed dates or city aliases, so `NO_MATCHING_RAW_CITY_DATE_ROWS` does **not** constitute global absence proof.
- Raw ATP singles validation still does NOT certify main draw, actual match start, ATP tier, verified player ID, or T−60 quote.
- The official calendar is **only February 2024**, not full official coverage of 2024 or 2022–2026.
- Keep user raw data out of Git. Provider states downloadable CSVs CC BY 4.0 with attribution: https://www.valuebetennis.com/en/donnees.htm .
- Even when every figure reconciles, the dataset remains blocked for XGBoost/market eligibility.

## Test-driven acceptance
Red-green subprocess and pure-function tests for valid month/source counts, source-hash mismatch, malformed schema, filtered WTA/Challenger candidate, event with no source rows, accepted source candidate, invalid dates, duplicate IDs, output overwrite and corrupted coverage count. Full 4/4 GitHub CI, no training/policy changes. User Windows real-file execution is a separate acceptance checkpoint.
