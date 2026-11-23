# P1.3c — Source-backed ATP edition-tier registry: design

**Status:** implementation design; user has approved continuing the ATP research workflow.
**Source inventory:** user-uploaded `valuebetennis_tournaments_2022_2026.json`, byte SHA-256 `eccb403bb6c0874e30f4e304c7be23678d2d1e6db095fd9174ee1753a225665b`. P1.3b report: 323 UTC-year groups, 19,065 candidate rows, 9 cross-year provider IDs, 23 special-event groups (416 rows), 3 missing raw final-code groups and a large start gap. This is not complete official tournament coverage.

## Architectural decision

Create a **reviewed-claims registry** checked by a pure, fail-closed `audit_tier_registry(inventory, registry, *, inventory_sha256)` function. The registry is an explicit, human-reviewed per-source `(utc_year, provider_tournament_id)` join to an independently researched official tournament tier. The key is *not* an official ATP edition identifier. For any cross-calendar-year provider ID, remain unreviewed until actual edition identity can be confirmed.

The audit must not authorize model training, infer qualifying/main-draw rounds, assume opening/closing quotes were available T−60, or fill missing events/results. For safety the only recognized `dataset_coverage` statuses are `UNVERIFIED` and `KNOWN_INCOMPLETE`; a reviewer cannot declare completeness solely from an inventory. The unreviewed 2024 Australian Open and Indian Wells examples stay known-incomplete even when an authoritative source proves tier.

## Registry schema
```json
{
  "registry_version": "P1_EDITION_TIER_REGISTRY_1",
  "inventory_sha256": "<exact original JSON bytes SHA-256>",
  "entries": [{
     "utc_year": 2025,
     "tournament_id": "14168",
     "observed_name": "Qatar ExxonMobil Open - Doha",
     "official_edition_year": 2025,
     "official_tier": "ATP_500",
     "dataset_coverage": "UNVERIFIED",
     "evidence_url": "https://www.atptour.com/en/news/atp-500-upgrades-from-2025",
     "evidence_note": "ATP explicitly upgraded Doha from ATP 250 to ATP 500 in 2025",
     "reviewed_on": "2026-11-23"
  }],
  "expected_absent_events": [{
    "official_edition_year": 2024,
    "official_event_name": "ABN AMRO Open - Rotterdam",
    "official_tier": "ATP_500",
    "evidence_url": "https://www.atptour.com/en/news/rotterdam-2024-history-draw-schedule",
    "reviewed_on": "2026-11-23"
  }]
}
```

Only `ATP_250`, `ATP_500`, `MASTERS_1000`, `GRAND_SLAM`, `OTHER` are valid `official_tier` values. A tier is a **reviewed assertion tied to a source URL**, not a machine-verified fact: the audit validates URL host and the registry structure, but cannot claim external independent verification merely from a URL string. `ATP_250` is history-only, `OTHER` out-of-scope, and ATP500/Masters/Slams only **potential target tier** pending round completeness, main draw, historical timestamp validation and coverage.

## Fail-closed invariants
- Explicit snapshot SHA-256 anchoring; reject mismatch (never silently reuse registry against regenerated provider exports).
- Each entry must match an existing `(utc_year,tournament_id)` and **exact original displayed tournament name** in P1.3a inventory. Reject duplicated join keys, missing/invalid IDs, invalid tier, fabricated source-domain string, missing review date or evidence note, and unknown/unsupported coverage state.
- A provider ID that appears in more than one UTC year **cannot be classified** by a per-calendar-year entry before a separate official-edition reconciliation is implemented. Reject rather than silently splitting/merging.
- `expected_absent_events` is documentary negative coverage evidence; if a named event is actually present for that UTC year, fail review rather than falsely saying absent. Do not auto-create missing event rows.
- Whole-source status remains `REVIEW_REQUIRED`. Report exact reviewed/unreviewed counts and count of reviewed target-tier rows that are `KNOWN_INCOMPLETE`. No auto-acceptance even if 323/323 tier claims existed.
- Source evidence URLs are *allowed-domain syntax checks only*, no live link verification; project docs record manually read primary source pages for initial seed.
- All `eligible_for_model_training=0`, `tier_mapping_verified=false` at **dataset level**, `main_draw_verified=false`, `t60_quote_verified=false`, `allocation_enabled=false`, `stake=0`.

## Current verified evidence (independently browsed 2026-11-23)
- ATP: Dallas/Doha/Munich upgrade **from 2025** (prior ATP250 -> ATP500): https://www.atptour.com/en/news/atp-500-upgrades-from-2025
- ATP: Indian Wells Masters1000: https://www.atptour.com/en/tournaments/atp-masters-1000-indian-wells/404/overview
- Australian Open: 2024 men's final held on **28 Jan 2024**; provider inventory has only Jan23 and lacks codes 10/12: https://ausopen.com/articles/news/sinner-winner-italian-takes-first-major-ao-2024
- ATP: Rotterdam 2024 ATP500, tournament absent from user's 2024 snapshot: https://www.atptour.com/en/news/rotterdam-2024-history-draw-schedule
- ATP 2025 calendar: https://www.atptour.com/en/news/what-is-the-2025-atp-tour-calendar

## Alternatives rejected
- Map all provider `Main tour` to ATP 500 (wrong, includes ATP250 and special events).
- Map all provider `Masters` to Masters1000 (wrong, includes ATP Finals).
- Set `main_draw_verified=true` based on `tour=4` or `tour>=4` without event-specific draw evidence.
- Auto-fix incomplete 2024 data with inferred results; introduces selection bias/label contamination.
- Commit local raw CSV or generated 250KB JSON and treat GitHub commit as a data licence grant.

## Acceptance
Test-first RED/GREEN for registry integrity, semantic tier classification across years, cross-UTC-year conflicts, known incomplete records, absent event checks and CLI output. Four CI jobs green. Run CLI with **the user's exact snapshot** post-merge; official 323-event mapping and main-draw reconciliation remain unsolved and tracked in issue #7.
