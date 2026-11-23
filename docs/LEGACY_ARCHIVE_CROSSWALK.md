# P1.4c — Valuebetennis legacy archive metadata crosswalk

**Scope:** A source-backed metadata join between **twelve actual ATP February 2024 event listings** in Valuebetennis's historical HTML tournament index and the already pinned official ATP February calendar. This does **not** restore matches, verify draws or create licensed match-level records.

## Confirmed input evidence

The user's original local `data/valuebetennis-matchs-2024.csv` (SHA-256 `09437d8208c937d9efb82af232edf6c6f8520be7ec2d6773dde71886b79c68ef`) was audited through P1.4b: **79,910 raw records, zero February-2024-dated records of any genre, zero invalid dates**, and 3,409 provisional ATP top-tour candidates matching the pinned five-season inventory. P1.4a independently compared 12 ATP official events to the inventory and confirmed 12/12 have no source candidate.

Sources checked on 2026-11-23:
- [Valuebetennis 2.0 legacy February 2024 tournament archive](https://www.valuebetennis.com/tournaments/2024/02/archive.htm): lists 12 men's `H` events in `Main tour` with legacy provider IDs.
- [ATP historical results archive 2024](https://www.atptour.com/en/scores/results-archive?year=2024): confirms actual February tour-level events.
- [ATP official 2024 final calendar](https://www.atptour.com/-/media/files/final-2024-atp-calendar.pdf): establishes ATP250 versus ATP500 event tier.
- [Valuebetennis public CSV exports](https://www.valuebetennis.com/en/donnees.htm): downloadable annual CSV files are CC BY 4.0 with attribution.
- [Valuebetennis database guide](https://www.valuebetennis.com/en/guide/base-de-donnees-tennis.htm): published CSV includes live-imported settled matches; retrospective imports are a separate population and not necessarily published.
- [Historical Valuebetennis terms](https://www.valuebetennis.com/cgv.htm): older paid services/legacy website terms. **Do not assume** the new CSV CC BY grant covers all historical HTML or detailed match pages.

## Exact legacy IDs from the archive index

| Official event | Legacy provider ID | Archive start date |
| --- | ---: | --- |
| Córdoba | 12492 | 2024-02-05 |
| Dallas | 12493 | 2024-02-05 |
| Marseille | 12494 | 2024-02-05 |
| Rotterdam | 12495 | 2024-02-12 |
| Buenos Aires | 12496 | 2024-02-12 |
| Delray Beach | 12497 | 2024-02-12 |
| Doha | 12542 | 2024-02-19 |
| Rio de Janeiro | 12543 | 2024-02-19 |
| Los Cabos | 12544 | 2024-02-19 |
| Dubai | 12570 | 2024-02-26 |
| Acapulco | 12571 | 2024-02-26 |
| Santiago | 12572 | 2024-02-26 |

Names in `docs/registries/valuebetennis_legacy_2024_02_crosswalk_v1.json` are the exact provider archive labels, not necessarily the ATP's branding. `categorie=Main tour` does **not** distinguish ATP 250/500; official tier is retrieved from the separate ATP calendar reference. Any retrospective provider ID is a **review hint**, not independently verified match or player identity.

## Windows PowerShell after PR merge

```powershell
git pull --ff-only
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m atp_gate valuebetennis-legacy-crosswalk reports\valuebetennis_tournaments_2022_2026.json docs\registries\atp_2024_february_official_events_v1.json docs\registries\valuebetennis_legacy_2024_02_crosswalk_v1.json --out reports\valuebetennis_legacy_crosswalk_2024_02.json
```

The CLI reads only three local JSON inputs, checks exact original inventory SHA-256 and per-event key/ID/name/city/date/sex/category consistency, and writes only an optional **separate** ignored JSON report. A stale source, missing/duplicate event key, wrong ID/date/city, or an attempt to overwrite an input yields `ERROR` and exit code 2.

Expected on the original snapshot: `LEGACY_CROSSWALK_REVIEW_REQUIRED`, 12 crosswalk rows and 12 archive IDs not present in the P1.3a source inventory. These figures **must be verified by the user's real-file CLI run** after merge; synthetic CI tests alone are not real-data acceptance.

## Source-rights decision and next action

| Data surface | Rights known | Decision |
| --- | --- | --- |
| Current downloadable annual Valuebetennis CSV | Provider declares CC BY 4.0 with attribution | Keep downloaded CSV locally with immutable SHA and attribution; scientific completeness still blocked |
| Legacy Valuebetennis tournament listing HTML | **Reuse rights for old HTML not independently verified** | Use this small source-linked index as manually reviewed evidence only; do **not** bulk-download or import old match pages |
| Legacy *match-detail pages* | Licensing, reliability and current availability not established | **BLOCK** any historical repair ingestion pending explicit authorization and match-level audit |
| Jeff Sackmann match results/mirrors | CC BY-NC-SA 4.0, noncommercial and share-alike | Only consider a separately licensed noncommercial research branch after obligations reviewed; no automatic substitution in commercial model |
| Tennis-Data.co.uk results | Site-specific terms, not a blanket ML/commercial licence | Require explicit rights review before programmatic import/ML use |

Provider-contact question for future authorization:

> Could you confirm whether the 2024 February ATP matches listed in the legacy tournament index (IDs 12492–12572) can be provided as a licensed downloadable match-level historical export? The current public 2024 season CSV contains no February-dated records. Please clarify permitted machine-learning/research and commercial reuse, whether the old HTML index and match-detail records are included in the CC BY 4.0 CSV grant, and what provenance or quality guarantees exist for historical retrospective imports.

Do not assume a reply or provider approval; no outgoing email was sent.

## Remaining P1.4 and P2 blockers

A verified **complete** ATP 2024 season needs independent licensed match outcomes with stable player identity and main-draw/round mapping, official result/draw reconciliation, absent-match and retirement treatment, and explicit per-event completeness. The current crosswalk cannot certify those fields or any T−60 market quote. No results are imputed. The outputs remain `legacy_archive_rights_verified=false`, `legacy_match_results_available=false`, `tier_mapping_verified=false`, `main_draw_verified=false`, `eligible_for_model_training=0`, `allocation_enabled=false`, `stake=0`.
