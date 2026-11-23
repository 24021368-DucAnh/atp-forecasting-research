# P1.4b — Investigate February 2024 gaps in the *raw* provider CSV

The 2022–2026 Valuebetennis P1.3a inventory is internally reconciled but missing all **12 official February 2024 ATP Tour events** (8 ATP250 + 4 ATP500) from its **accepted source-candidate groups**. The user's confirmed P1.4a CLI reports `COVERAGE_REVIEW_REQUIRED` with `missing_official_events: 12`. That by itself does not explain where data disappeared.

The new `valuebetennis-gap-forensics` command inspects a **single original seasonal CSV** and distinguishes rows that were never observed under a strict city/date match from rows found but excluded by the current ATP source filters. It never reconstructs match results or gives training permission.

## Windows PowerShell after merging PR

In the existing project folder:

```powershell
git pull --ff-only
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m atp_gate valuebetennis-gap-forensics data\valuebetennis-matchs-2024.csv reports\valuebetennis_tournaments_2022_2026.json docs\registries\atp_2024_february_official_events_v1.json --month 2024-02 --out reports\valuebetennis_raw_gap_2024_feb.json
```

This reads **only** the existing CSV from local `data/`. The full report is saved under ignored `reports/`; a small summary is printed. No source files or results are rewritten. The CLI rejects output paths equal to any input.

## What to investigate in JSON

- `source_file.sha256` and `size_bytes`: exact bytes must match the `source_files` manifest of the original pinned P1.3a JSON. This proves internal **snapshot consistency**, not independent authentication against the provider's website.
- `source_total_rows`: all CSV rows in this one file.
- `source_provisional_accepted`: accepted ATP top-level provisional matches under **the existing P1.2 filter order**, independently reconciled to `coverage.by_source[CSV basename]`.
- `month.raw_rows`: all records with parsable UTC timestamps in February 2024, **including WTA and Challenger**. `month.by_genre`, `month.atp_by_raw_category`, `month.filter_reasons` explain where these records come from.
- `undated_rows_outside_month_attribution`: invalid/missing dates across the whole CSV. They cannot be assigned to February; a zero February total never proves those rows are irrelevant.
- `official_event_diagnostics[]`: per official February ATP event, number of raw city/date-hint rows and rejected reason totals. Statuses are `NO_MATCHING_RAW_CITY_DATE_ROWS`, `ONLY_FILTERED_RAW_CANDIDATES` or `ACCEPTED_SOURCE_CANDIDATE_PRESENT`. Even the latter is **not** an official tournament ID match or a verified main draw.
- `source_rejection_counts`: overall input filtering by reason, including other circuits, other categories, bad IDs, invalid winner/round/time, duplicates.

**Crucial:** raw tournament names may use aliases, venue changes or abbreviations; only a strict `' - CITY'` suffix (accent-normalized) within the official event period ±4 days is considered. An unmatched raw record is not proof that the official event was absent. The analyzed file is **one annual local source**, not all five seasons.

## How results affect P1.4c

1. If February contains ATP `Main tour`/`Masters`/`Grand Slam` rows that fail identity/round/date/winner validation, first inspect and correct documented ingestion errors **with tests**, not by guessing values.
2. If city/date matching finds WTA/Challenger only, report the distinction and continue investigating the real official ATP event. Do not reinterpret Challenger as ATP500.
3. If no strict city/date candidates are found, compare raw source aliases and season snapshots with legally reusable official match results. Missing events/rounds **may never be silently imputed**.
4. Separately validate 2024 AO/Indian Wells main draw and skipped events, plus cross-year event ID mapping; do not feed incomplete selections into walk-forward.

Provider attribution: [Valuebetennis, Tennis results and odds since 2021](https://www.valuebetennis.com/en/donnees.htm), states CC BY 4.0. Its opening/closing odds cannot establish an authentic T−60 market price.

`RAW_SOURCE_FORENSIC_REVIEW_REQUIRED` means inspection finished, not provider data accepted. Every audit has `eligible_for_model_training: 0`, `tier_mapping_verified: false`, `main_draw_verified: false`, `t60_quote_verified: false`, `allocation_enabled: false`, `stake: 0`.
