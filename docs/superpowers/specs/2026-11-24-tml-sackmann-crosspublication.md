# P1.4d — TML ↔ Jeff Sackmann Archive Cross-Publication Audit (2026-11-24)

**Goal:** Reproduce the observed 340/340 February 2024 match-identity comparison without confusing provider ID namespaces or treating a likely derived mirror as independent ATP official validation. **Mode:** PRIVATE_NONCOMMERCIAL_RESEARCH.

**Observed evidence:** TML GitHub 2024 `2024.csv` blob SHA-1 `cf513429259b4a15e84e2021206895d9bd4ff772`; Aneeshers/tennis-sackmann-archive `atp/atp_matches_2024.csv` blob `c401319bc1dec4633dd2c730aa5a7a7376e176f8`. Both 3,076 rows. TML 50 columns, Sackmann 49; their IDs and match numbering differ. Twelve official February tournament candidates contain 340 rows. With **explicit two player display-name aliases** and numeric tournament code normalization: 340/340 event/winner/loser/round match and 339/340 exact score strings. One Buenos Aires QF retirement text `4-6 7-5 RET` vs `4-6 7-5 0-0 RET`. No official ATP match/date proof.

## Approach
1. Direct join on player ID or `match_num`: **rejected**; TML IDs alphanumeric (e.g. DA31), Sackmann IDs numeric (106198), and tournament IDs may have left zero padding.
2. Fuzzy name matching without approvals: **rejected**; can silently turn different players into same entity.
3. **Selected:** source-specific tournament ID normalization on numeric suffix only, deterministic Unicode/case/punctuation normalization of display names, an explicit allowlisted alias file for exactly the known name variants, and exact round pairing. Preserve score text discrepancy as finding, never fabricate/correct a result.

## Interfaces
- `audit_tml_sackmann_crosspublication(tml_path:Path, archive_path:Path, crosswalk:dict, aliases:dict)->dict` in `src/atp_gate/tml_sackmann_crosscheck.py`.
- Input crosswalk = twelve official TML February 2024 event refs; aliases file = `docs/registries/tml_sackmann_2024_player_aliases_v1.json` mapping TML display-name tokens to Sackmann display-name tokens.
- Both input CSV original bytes SHA256 hashed, 20 MiB max, UTF8, expected column schema. No network or default provider download in this module.
- Reject duplicate key `(normalized_event_id, normalized_winner_name, normalized_loser_name, round)`, nonnumeric/empty player name, missing round, unrecognized alias registry version, ambiguous many-to-one alias or target input alias collision.
- Score discrepancies *report only*, including retirement formatting. Do not treat `RET` as a completed match or use those score strings as predictive features.
- Return per-event aggregate counts, matched names+round, exact score matches, mismatched scores; no serialized players/score rows. `status=CROSS_PUBLICATION_AGREEMENT_REVIEW_REQUIRED` only if 340 of 340 official candidates correspond, all 12 event counts meet the pinned registry, and there are no unmatched players or identities. `status=CROSS_PUBLICATION_CONFLICT_REVIEW_REQUIRED` otherwise. Every output `official_match_draw_verified=false`, `source_independence_verified=false`, `individual_match_start_verified=false`, `eligible_for_model_training=0`, `allocation_enabled=false`, `stake=0`.
- All source data are CC BY-NC-SA or personal noncommercial; no raw CSV redistribution. Source lineage may overlap; do not call it an independently certified official source.

## Tests & acceptance
Synthetic 12-event fixture with explicit aliases, score disagreement, provider ID padding and changed match numbers, duplicate match, changed winner/loser, missing event, conflicting alias, header drift and no raw row leak to report. RED→GREEN full GitHub CI 4/4. Real-source observation documented in Issue #17 but Python CLI original-byte acceptance remains separate.
