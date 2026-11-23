# P1.4a — Official ATP Event Calendar Coverage Preflight (Design)

**Date:** 2026-11-23
**Scope:** A strict source-quality and coverage comparison. The program must not train a model, reclassify player/match labels, enable real allocations, or claim market advantage.

## Background: real source evidence

The user's 2022–2026 Valuebetennis P1.3a inventory contains 323 UTC-year groups and 19,065 provisional ATP candidate rows, pinned by SHA-256 `eccb403bb6c0874e30f4e304c7be23678d2d1e6db095fd9174ee1753a225665b`. P1.3c reviewed 11/323 tier entries. We independently inspected the original uploaded JSON: **2024 has no groups with observed match times in February**. Official ATP 2024 results archive and ATP-published final calendar list **12 ATP Tour singles tournament events scheduled in February 2024** (8 ATP250 and 4 ATP500), from Córdoba / Dallas / Marseille through Acapulco / Dubai / Santiago. The complete 2024 season plainly cannot be considered present.

Primary sources:
- https://www.atptour.com/en/scores/results-archive?year=2024 (actual events)
- https://www.atptour.com/-/media/files/final-2024-atp-calendar.pdf (published event tiers/draws, with potential schedule changes; compare to archive)
- https://www.atptour.com/en/news/rotterdam-2024-history-draw-schedule (Rotterdam ATP500)

## Chosen architecture

A **separate read-only** `audit_official_calendar_coverage(inventory, official_calendar, *, inventory_sha256)` takes the saved P1.3a tournament inventory (not raw provider CSVs) and a small *manually source-checked* official schedule reference JSON. It reuses `review_tournament_inventory` to validate all 323 rows/counts and source safety flags before accepting the comparison. No heuristic tournament ID reconciliation or automatic tier assignment occurs.

The reference JSON schema:
```json
{
  "calendar_version":"P1_OFFICIAL_EVENT_CALENDAR_1",
  "inventory_sha256":"<exact original JSON file SHA256>",
  "scope":"CURATED_OFFICIAL_EVENTS_ONLY",
  "events":[{
    "event_key":"ATP_2024_ROTTERDAM",
    "official_year":2024,
    "official_event_name":"ABN AMRO Open",
    "official_tier":"ATP_500",
    "city":"Rotterdam",
    "start_date":"2024-02-12",
    "end_date":"2024-02-18",
    "results_archive_url":"https://www.atptour.com/en/scores/results-archive?year=2024",
    "tier_source_url":"https://www.atptour.com/-/media/files/final-2024-atp-calendar.pdf",
    "reviewed_on":"2026-11-23"
  }]
}
```

The city/date comparison is a conservative **potential source-match detector**, not authoritative tournament identity: matching the normalised suffix after `' - '` to official city and overlapping expected event dates +/- 4 calendar days gives `SOURCE_CANDIDATE_UNVERIFIED`, not `VERIFIED`. Zero possible matches gives `NO_SOURCE_EVENT_CANDIDATE`; >1 gives `AMBIGUOUS_SOURCE_CANDIDATES`. Explicitly flag if any group with a matching city is outside expected dates. Calendar references do not automatically assert main-draw coverage, player IDs or missing results.

## Safeguards and validation
- Exact SHA-256 source snapshot matching, with original full P1.3b count reconciliation and `stake=0` hard flags.
- Every official event has unique `event_key` + unique year/city/time window, positive year, plausible ISO start/end dates, known ATP/Grand Slam category, and explicit independent official results and tier URLs. Reject userinfo, non-HTTPS, lookalike domains, query-string/junk URLs beyond allowed official sources. This checks link syntax, not external content.
- Only published curated official events included; **do not claim coverage for all of 2024 or any other season based on a 12-event February subset**. Never auto-add detected missing matches or calendar entries to the existing tier registry.
- Track accepted source group candidates by provider ID/year/name, observed match count and dates. Do not call them verified identities or verified event editions.
- Output a deterministic `COVERAGE_REVIEW_REQUIRED` report, counts by official tier, flagged missing event keys, year-month breakdown and all source hashes; all model eligibility remains zero.
- CLI: `python -m atp_gate valuebetennis-calendar-audit SOURCE_INVENTORY.json OFFICIAL_CALENDAR.json [--out reports/...]`. Prints compact summary and optionally writes full report; never overwrites original files. On a valid reference with missing events the command returns 0 (audit succeeded, data still blocked); invalid source/schema/stale digest returns 2.
- No data/raw files added to Git; only this small curated official event-reference ledger, code, tests and docs.

## Rejected alternatives

1. Guess all 323 tournament tiers from names and source `categorie`: fails both ATP250/ATP500 and special-event cases.
2. Use ATP's *planned* calendar as an automatic final truth: tournaments relocate or change dates; here each seed entry has also been cross-checked against actual **results archive**.
3. Treat 2024 `observed_years=[2024]` as completeness or impute 12 missing February results: invalid selection and labeling.
4. Use normalized venue matching as an approved registry join: there can be simultaneous or renamed events; a match can only be a manual-review candidate.

## Acceptance

TDD RED/GREEN for snapshot drift, false calendar event, wrong year, missing official evidence, date mismatch and two same-city source matches. The official 2024 February seed must have 12 unique events, exactly 4 ATP500 and 8 ATP250 and official citations. Four GitHub Actions Windows/Ubuntu Python3.11/3.12 pass. The user can then run the command on their original JSON; expect **12/12 NO_SOURCE_EVENT_CANDIDATE** for this snapshot, but that remains a user-run acceptance check until observed.
