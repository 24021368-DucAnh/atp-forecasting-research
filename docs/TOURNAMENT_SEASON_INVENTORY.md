# P1.3a — Valuebetennis tournament-season and draw-round inventory

## Purpose

Before converting Valuebetennis source records into the ATP Selective Forecasting Lab's modeling input, produce one **read-only tournament-year catalog** keyed by provider `tournoi_id` and **UTC match year**.

This is an intermediate evidence collection step, not an official ATP event registry. It never infers ATP 250 or 500 from `categorie=Main tour`, nor main-draw status from a hardcoded provider `tour` threshold. It does not add match time verification or T−60 quotes.

## Windows PowerShell 5.1 — five actual seasonal files

After the PR is merged and `git pull --ff-only`:

```powershell
.\.venv\Scripts\python.exe -m atp_gate valuebetennis-tournaments --out reports\valuebetennis_tournaments_2022_2026.json --start-year 2022 --end-year 2026 data\valuebetennis-matchs-2022.csv data\valuebetennis-matchs-2023.csv data\valuebetennis-matchs-2024.csv data\valuebetennis-matchs-2025.csv data\valuebetennis-matchs-2026.csv
```

The CLI prints a **small summary** rather than flooding PowerShell with hundreds of tournament records. Full records are saved in `reports\valuebetennis_tournaments_2022_2026.json`, which remains ignored by Git.

- `INVENTORIED_UNMAPPED`, exit 0: all expected years observed, all accepted provisional candidates grouped by positive tournament ID, and no within-year tournament metadata conflicts.
- `INCOMPLETE`, exit 2: missing expected years, missing tournament IDs/names, no inventoriable candidates, or conflicting same-ID/same-year name/category/surface claims.
- `ERROR`, exit 2: unreadable files, bad schema or invalid input arguments.

## Full JSON source

`tournament_inventory.tournament_seasons[]` includes:
- `year` (UTC match year), `tournament_id` (raw provider positive numeric ID)
- `names`, `categories`, `surfaces` as **sets of original observed values**, not guessed canonical types
- `round_counts` grouped by provider's **raw 0–12 round codes**, without translating them into qualifiers/main draw
- Candidate match count, first/last recorded UTC, contributing file basenames and `metadata_conflict` flag
- `official_tier: null`, `main_draw_verified: false` on every record.

`tournament_inventory.summary` reconciles total provisional candidates with inventoried candidates and counts missing tournament metadata and conflicting event keys. The parent report retains original source SHA-256s, date coverage, missing odds information and the hard safety flags.

## Observed actual-data baseline

User ran P1.2 against five locally downloaded season CSVs on 23 November 2026 and reported:
- 414,878 total raw rows, 19,065 ATP provisional candidates, no candidate match-ID duplicates
- 2022 4,060; 2023 4,089; 2024 3,409; 2025 3,918; 2026 3,589
- 9,814 `Main tour` candidates, 4,642 `Masters`, 4,609 `Grand Slam`; **these are not all proven main draw**
- 327 missing opening pairs, 1,582 missing closing pairs; neither opening nor closing prices proves T−60.

The sum of raw rows aligns with the provider's French open-data 22 November 2026 snapshot (83,381 + 89,826 + 79,910 + 80,412 + 81,349 = 414,878). Reference: https://www.valuebetennis.com/donnees.htm. This aggregate cross-check does **not** independently authenticate the user's source file hashes or per-season byte content. The English page reflected a 21 November 2026 snapshot with 100 fewer 2026 rows.

## Next evidence-dependent step

Use the exported tournament-season catalog to assemble a separate reviewed registry of **official** tournament tiers, supported by year-specific ATP/Grand Slam schedules and source URLs. Investigate the actual provider's numeric `tour` semantics by specific event and bracket and independently verify main-draw membership; do not guess a universal round threshold.

A future **separate** adapter may use only verified events/rounds and stable IDs for chronological historical evaluation. The report produced here remains `eligible_for_model_training: 0`, `tier_mapping_verified: false`, `main_draw_verified: false`, `t60_quote_verified: false`, `allocation_enabled: false`, `stake: 0`.
