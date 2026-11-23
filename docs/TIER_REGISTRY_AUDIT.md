# P1.3c — Source-backed ATP tier claims and coverage gates

## What it does

The `valuebetennis-tier-audit` command joins a *small manually researched* registry of tournament tier assertions to **one exact-byte SHA-256** of your P1.3a `valuebetennis_tournaments_2022_2026.json`.

It checks tournament ID + UTC match year + exact source name, review date, HTTPS official evidence URL, dataset coverage claim and absent-event markers. It compares against an independently reconciled inventory. It is intentionally an **incremental editorial review ledger**, not a finished map of 323 official editions or an ML-ready dataset.

## Windows PowerShell (run after PR is merged)

```powershell
git pull --ff-only
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m atp_gate valuebetennis-tier-audit reports\valuebetennis_tournaments_2022_2026.json docs\registries\valuebetennis_2022_2026_tiers_v1.json --out reports\valuebetennis_tier_audit_2022_2026.json
```

If the inventory was regenerated or edited, the digest differs and this command **exits code 2 (ERROR)**. This is deliberate: do not copy over a stale registry hash; rerun source-quality inspection and review differences first. The audit never overwrites its source inventory or registry.

`REVIEW_REQUIRED` with exit 0 indicates the review ran successfully, **not** that tiers, official event years, main-draw boundaries, full seasons or market prices have all been verified. The full audit JSON is saved only to ignored local `reports/`, and includes every **unreviewed** event key as an explicit queue.

## Official sources used for the initial claims

- 2025 tier upgrades, Dallas/Doha/Munich — ATP press release, 2023-11-08: https://www.atptour.com/en/news/atp-500-upgrades-from-2025
- 2025 calendar lists upgraded 500 tiers: https://www.atptour.com/en/news/what-is-the-2025-atp-tour-calendar
- 2026 calendar lists Dallas, Doha and Munich as ATP 500: https://www.atptour.com/en/news/what-is-the-2026-atp-tour-calendar
- Indian Wells ATP Masters 1000 overview: https://www.atptour.com/en/tournaments/atp-masters-1000-indian-wells/404/overview
- Australian Open 2024 official men’s singles final on **28 January**: https://ausopen.com/articles/news/sinner-winner-italian-takes-first-major-ao-2024
- Rotterdam 2024 (ATP 500), **absent in user’s 2024 inventory**: https://www.atptour.com/en/news/rotterdam-2024-history-draw-schedule

The selected `utc_year`/provider `tournament_id`/display name combinations come from the user-uploaded inventory, not from ATP official IDs. The seed does **not** claim that a link automatically proves the assertion: a researcher checked source page contents for the initial claims. Future additions require the same manual evidence review and exact join.

## Current dataset hazards (must not be suppressed)

- Snapshot contains 323 UTC-year groups / 19,065 ATP *provisional* source candidates.
- Nine repeated provider event IDs across UTC new-year boundaries. A provider ID can span December and January of one official tournament edition; **do not map either half** until independently resolved.
- Raw provider labels cover mixed/team/experimental events, including Nitto ATP Finals incorrectly grouped with Masters if treated as an ATP Masters 1000. Names alone are not safe general exclusion rules; no automated blanket mapping.
- 2024 Australian Open rows stop Jan 23 and lack raw semifinal/final codes; the official Jan 28 final exists. Tier `GRAND_SLAM` can be source-backed while coverage remains `KNOWN_INCOMPLETE`.
- 2024 Indian Wells has only 47 provisional rows, vs 2023 131, so tier `MASTERS_1000` does **not** authorize those rows for modeling.
- 2024 Rotterdam ATP 500 is absent from the entire 2024 inventory, preventing full season coverage.
- `dataset_coverage=UNVERIFIED` does **not** mean complete; `KNOWN_INCOMPLETE` explicitly blocks completeness.
- Provider opening/closing odds are not verified T−60, and calendar event dates are not first-serve verification.

## Trust and approval layers

1. **Local inventory integrity**: SHA-256 anchored and counts reconciled.
2. **Source-backed tier claim**: explicit official source URL and reviewed date for a single event/UTC year. *URL hostname validation is not live content verification.*
3. **Correct event edition**: external calendar/season reconciliation (unresolved for cross-UTC-year IDs).
4. **Match eligibility**: official bracket round mapping + main-draw and single-event completeness; still unresolved.
5. **Out-of-time validation and market quotes**: not covered; must compare chronological Elo/XGB against market with reliable same-time odds and uncertainty estimates.
6. **Stake allocation**: remains disabled in all outputs; no real-money betting recommendation.

The current tool cannot skip levels 3–6. `eligible_for_model_training=0`, `tier_mapping_verified=false` at full-dataset level, `main_draw_verified=false`, `t60_quote_verified=false`, `allocation_enabled=false`, `stake=0` are enforced.

## What to do if snapshot changes

Regenerate P1.3a and P1.3b reports, diff all tournament ID/year/name/round/date changes, record revised hashes, and rebuild **only reviewed** entries for the new version. Never silence the digest mismatch or impute missing historical results. Track in GitHub Issue #7.
