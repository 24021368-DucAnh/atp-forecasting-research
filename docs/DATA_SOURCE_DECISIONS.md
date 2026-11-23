# P1 historical ATP source decisions and rights audit

**Checked:** 2026-11-23. **Purpose:** document provenance and restrictions before acquiring multi-season data. A dataset being publicly accessible does **not** imply blanket permission to train or redistribute.

| Candidate | Provider statement / source | Observed schema / coverage | Training-use decision |
| --- | --- | --- | --- |
| Existing historical 2026 data (mirrored Tennis-Data-style CSV) | https://www.tennis-data.co.uk/data.php | `Date`, `Series`, `ATP` tournament ordinal, `Winner`, `Loser`, `WRank`, `LRank`, `B365W`, `B365L`; day precision | **Rights not verified.** Tennis-Data currently describes individual private use and expressly excludes commercial/AI training products. A GitHub mirror is not a license grant. Keep existing work research-only and do not redistribute; obtain permission before broader planned use. |
| Valuebetennis seasonal CSVs (2021–2026) | https://www.valuebetennis.com/en/donnees.htm | Semicolon-separated source; ATP/WTA singles, `match_id`, `joueur1_id`, `joueur2_id`, `vainqueur_id`, UTC `date`, surface, `categorie`, `tour`, opening and closing Pinnacle odds | **Preferred *candidate* for separate adapter investigation.** Site publishes CC BY 4.0 with attribution. Verify actual file/schema/coverage and the up-to-date license text before use. |
| Jeff Sackmann ATP archive / mirrors | https://github.com/sportData/tennis_atp | Rich ATP player/match statistics in yearly CSVs; possible supplemental features | **Noncommercial/ShareAlike constraints.** Dataset commonly released CC BY-NC-SA 4.0, and a mirror does not remove restrictions. Reconfirm provenance before any use. |

## Material blockers

1. **Category ambiguity:** Valuebetennis describes `categorie` as categories such as `Main tour`, `Masters`, `Grand Slam`, rather than an unambiguous ATP 250/500 indicator. A non-versioned name lookup or a guess that all `Main tour` entries are ATP 500 would silently contaminate our requested evaluation tiers. Require an independently validated tournament-season ID → official tier mapping, with unmapped cases excluded.
2. **Qualifying/doubles/other circuits:** Verify `genre=atp`, singles main-draw and correct round taxonomy before including source rows. The publicly published Valuebetennis overview mentions ATP/WTA singles, but category alone does not certify ATP top-tour main draw.
3. **T−60 not established:** Valuebetennis `cote*_ouverture` and `cote*_cloture` are opening and last-before-start odds, not a timestamped quote observed at T−60. Its `date` is UTC, but does not by itself certify actual first serve.
4. **Player identity:** IDs must be validated for uniqueness and continuity across seasons. Existing `source_row` uses names only, which are NOT canonical IDs.
5. **Partial-year and snapshot revisions:** Valuebetennis says seasonal exports are regenerated; record download date, URL, SHA-256, row count, observed min/max date and any changes before comparisons.
6. **Source-specific data contract:** Do not feed Valuebetennis's French field names, `categorie`, or `tour` directly to the current Tennis-Data-style loader. Write a separate verified adapter after examining raw example records; do not invent a tier mapping.

## Attribution to retain if approved

Valuebetennis, Tennis results and odds since 2021, https://www.valuebetennis.com/en/donnees.htm (CC BY 4.0 as stated by provider).

## Current project policy

- No third-party CSV or XLSX bytes are committed; `data/` and `reports/` remain git-ignored.
- Source quality profiling and training are different operations; a `PROFILED` data inventory means neither license approval nor market edge.
- For the existing 2026 partial-year experiment, source SHA-256 is `a9ff61474edcdd69b14333f02cbcf6ba21b5cf24e75080e2214e507e336a0c13` and `source_identity_verified=false`.
- No source is allowed to create an `allocation_enabled=true` report. Research remains paper-only.


## P1.4c source-permission finding (2026-11-23)

**Empirical Windows source evidence:** the original pinned `valuebetennis-matchs-2024.csv`
(SHA256 `09437d8208c937d9efb82af232edf6c6f8520be7ec2d6773dde71886b79c68ef`)
contains **79,910 rows, no February 2024 UTC-dated row in any circuit and
no undated rows**. The provisional ATP source filter accepts 3,409 rows,
exactly matching the original P1.3a inventory manifest. This excludes the
*current* filter as the cause of missing **February-dated** records in this
specific source snapshot; it does not prove why they are absent upstream.

**Valuebetennis legacy website:** the separate
[February 2024 tournament index](https://www.valuebetennis.com/tournaments/2024/02/archive.htm)
lists twelve ATP male `Main tour` tournament IDs including Rotterdam 12495,
Dallas 12493, Doha 12542, Acapulco 12571. This is small event **metadata**,
NOT an export of match outcomes, verified main draw or permission to bulk
extract historical match-detail pages. The
[CC BY 4.0 CSV licence](https://www.valuebetennis.com/en/donnees.htm)
explicitly describes the downloadable **season CSV files**; do not presume
it extends to legacy HTML. The
[provider guide](https://www.valuebetennis.com/en/guide/base-de-donnees-tennis.htm)
distinguishes live-imported CSV results from less reliable retrospective
imports which are not necessarily published.

**Decision:** keep the pinned legacy HTML **index-only** crosswalk in
`docs/registries/valuebetennis_legacy_2024_02_crosswalk_v1.json`;
do not fetch/scrape old match pages, add their results or relabel source
permissions without the provider's explicit reuse terms and a separate
match-level provenance/quality review. Alternate Sackmann results are
CC BY-NC-SA 4.0 (noncommercial with ShareAlike); Tennis-Data.co.uk
rights are provider-specific. Any independent correction must be kept
separately identified, signed off for allowed use and verified against
official match draws. Zero training permission remains for the new source.
