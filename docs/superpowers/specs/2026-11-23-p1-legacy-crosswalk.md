# P1.4c — Legacy-provider archive metadata crosswalk (design)

Date: 2026-11-23. Baseline: P1.4b independently passed on the user's original 2024 CSV; SHA256 `09437d8208c937d9efb82af232edf6c6f8520be7ec2d6773dde71886b79c68ef`, 79,910 raw rows, 3,409 ATP provisional candidates, **0 raw dated rows in 2024-02**, 0 undated rows, 12/12 ATP official Feb events absent. Source five-season tournament inventory SHA256 `eccb403bb6c0874e30f4e304c7be23678d2d1e6db095fd9174ee1753a225665b`.

## Relevant independently checked source findings

- Valuebetennis legacy tournament *index* `https://www.valuebetennis.com/tournaments/2024/02/archive.htm` lists all 12 ATP February 2024 tournaments, with archived `tournoi_id`, date, name, `H` sex marker, `Main tour` category. These are TOURNAMENT METADATA, **not match-level results**.
- Current CSV download page `https://www.valuebetennis.com/en/donnees.htm` specifically grants CC BY 4.0 to **downloaded season CSV files**. Do not assume that statement grants reuse or scraping of the older archive HTML or match pages.
- Guide `https://www.valuebetennis.com/en/guide/base-de-donnees-tennis.htm` separates live-imported, published results CSV from retrospective imports, which are not necessarily distributed or equally reliable. This makes the different data populations plausible, **not a verified root-cause explanation for February**.
- Sackmann historic data/mirrors use CC BY-NC-SA 4.0; tennis-data.co.uk has distinct terms. Neither is a default licensed fix for eventual commercial ML.

## Chosen architecture

A standalone `audit_legacy_archive_crosswalk(inventory, official_calendar, legacy_manifest, *, inventory_sha256)` from `src/atp_gate/legacy_archive_crosswalk.py`. It first invokes the existing `audit_official_calendar_coverage` for source inventory count reconciliation, snapshot hash and official-calendar validation. A curated, SMALL **12-row metadata-only manifest** records legacy index values keyed by **official event_key**, not player/match data. The function validates each legacy row against the official event's name-city suffix and start date range plus or minus 4 days, confirms that legacy provider ID is not present in current pinned source for the same UTC-year, and checks unique event keys and IDs. All 12 official Feb events must be accounted for by the manifest (no silent missing or extra crosswalk rows).

JSON schema:
```json
{
 "manifest_version": "P1_LEGACY_INDEX_CROSSWALK_1",
 "inventory_sha256": "<exact original P1.3a snapshot>",
 "archive_url": "https://www.valuebetennis.com/tournaments/2024/02/archive.htm",
 "archive_record_type": "HISTORICAL_TOURNAMENT_INDEX_ONLY",
 "archive_page_rights": "UNVERIFIED_NOT_CSV_CC_BY_GRANT",
 "entries": [{
  "official_event_key": "ATP_2024_ROTTERDAM",
  "legacy_provider_tournament_id": "12495",
  "legacy_tournament_name": "ABN AMRO Open - Rotterdam",
  "legacy_start_date": "2024-02-12",
  "legacy_sex_marker": "H",
  "legacy_category": "Main tour",
  "evidence_url": "https://www.valuebetennis.com/tournaments/2024/02/archive.htm"
 }]
}
```

The archive is a **source metadata hint** only; even with a 12/12 key, ID and date match, the tool must never declare `event_identity_verified`, `licensed_match_rows`, `match_data_available`, `main_draw_verified`, `eligible_for_model_training` or `allocation_enabled` true.

## Rejected alternatives

- Parse/scrape full legacy match-detail webpages to populate training labels: permission and provenance of those pages unverified; index is not evidence matches exist.
- Assume the archive HTML contents are included in CC BY 4.0 CSV grant: ungrounded.
- Guess retrospective match outcomes or add missing February records from tournament names: fabricated data.
- Automatically merge the archive ID with current per-match provider IDs, or invent main draw/round selection.
- Treat the historical tournament index as proof of completed ATP results.

## Outputs

`status=LEGACY_CROSSWALK_REVIEW_REQUIRED`, 12 official event rows with legacy provider IDs, reason `LEGACY_INDEX_ONLY_NOT_MATCH_DATA`, source CSV/official-event audit statuses and names, count of IDs absent from current inventory. All metadata sourced from a reviewed legacy listing; report `legacy_archive_rights_verified=false`, `legacy_match_results_available=false`, `source_file_origin_verified=false`, `tier_mapping_verified=false`, `main_draw_verified=false`, `t60_quote_verified=false`, `eligible_for_model_training=0`, `allocation_enabled=false`, `stake=0`.

CLI `python -m atp_gate valuebetennis-legacy-crosswalk INVENTORY.json OFFICIAL_CALENDAR.json LEGACY_MANIFEST.json [--out reports/...]`. Reads only local source JSONs and writes an optional separate report; output path must not equal any of the three inputs. CLI errors on bad hash, unknown/duplicate official event keys or provider IDs, wrong source year/city/date/sex/category, or wrongly labelled rights.

## Acceptance

- RED test run proves missing module and later CLI.
- Valid fixtures assert 12/12 legacy IDs can be reviewed but **no match has been restored**.
- Negative cases for stale SHA, duplicate IDs, WTA marker `F`, wrong date, inconsistent city, false rights, and IDs that already appear in P1.3a inventory. No data/model changes.
- All Windows/Linux 3.11/3.12 CI green, no raw CSVs committed.
- After merge, Windows replay on the pinned user JSON is a separate actual-source evidence gate. P1.4 overall remains blocked until an independently licensed, match-level, main-draw verified source exists.
