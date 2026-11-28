# V4 S8 — Multi-source incremental ATP data activation design

Status: PROPOSED, PRE-ACTIVATION ONLY. Baseline accepted S1–S7 main
c66847471d2cc61241700f223b91c5e3d2cdc4d5, tree
3afe8ea953c03260c9b58958c6cdc7867d03e5db. PR #73 postmerge
45934447685. Binding design: 2026-11-26-v4-local-dashboard-design.md.
This proposal does not override that design, change V3, or grant rights.
No live fetch, real database population, real training, promotion or
scheduler activation has been performed in this preflight.

## Goal and non-goals

Discover broad sources of ATP men's singles fixtures, results and
metadata; accumulate new observations rather than repeatedly importing
all history; reconcile conflicting sources and preserve provenance.
Run on the existing single-user Windows, SQLite and local worker
architecture. Preserve offline historical and synthetic demonstrations.
The target is one deduplicated, time-aware match warehouse, not a
web-wide crawler. Include a source only for the operations its actual
terms permit. No bypass of authentication, rate limits, robots or other
access restrictions; no bulk capture from expressly prohibited sites.
No betting or raw redistribution. Price default zero; a paid plan
requires separately approved quote.

## Approaches

1. Single CSV source: inexpensive and already supported by P1.5,
   but cannot by itself verify upcoming fixtures or actual first serve.
2. Multi-source adapters with a rights registry and observation ledger:
   recommended. Reuse the existing updater; add independently eligible
   sources by capability, cross-check match identities and timing.
3. Indiscriminate HTML crawling: rejected. Unbounded network, unclear
   permissions, duplicated upstream feeds, schema drift and weak timing.

## Source inventory (public documentation reviewed 2026-11-28)

The following is a discovery inventory, NOT an authorization receipt.

| Source | Discovery evidence | Potential role | Decision |
| --- | --- | --- | --- |
| TennisMyLife | https://stats.tennismylife.org/tennis-match-database ; https://tennismylife.github.io/TML-Database/ | ATP results and statistics, documented downloadable CSVs; current year/ongoing export | First candidate. Public personal/educational/noncommercial terms, upstream rights caveat. Existing P1.5 explicit local updater remains separate; no new V4 use approved. Tournament start date is not individual match start. |
| Valuebetennis | https://www.valuebetennis.com/en/donnees.htm | Seasonal results, stable provider IDs, UTC date | CC BY 4.0 applies to described CSV exports, with attribution; not blanket permission for HTML. Prior 2024 February gap and tier ambiguities remain. Actual start/publication semantics unverified. |
| SportStatsAPI | https://sportstatsapi.com/legal/terms/ ; https://sportstatsapi.com/developers/free-tennis-api/ | Fixtures/results via authorized API, potential supplemental timing | Free noncommercial plan; terms sections 8/9 permit stated uses subject to others' rights; section 12 disclaims supplier-rights guarantees. Free data delay and timestamp semantics unresolved. No account/key/purchase. |
| Wikidata | https://www.wikidata.org/wiki/Wikidata:Licensing | Supplemental entity metadata/crosswalk only | Structured data CC0; not an authoritative match timing or completeness source. Validate entity identity and service access policy independently. |
| ATP Tour | https://www.atptour.com/en/terms-and-conditions | Official contextual reference / permitted manual verification if authorized | Terms prohibit systematic retrieval to compile database without express prior written permission. Do not add automated collector. |
| Other tournament, score and result sites | Discover documentation and terms individually | Potential fixtures, timing, independent corroboration | Default BLOCKED; no spider, bulk retrieval or presumption that publication grants reuse. |

Source independence must be demonstrated; two aggregators can share the
same upstream feed. Do not vote by count. Existing V3 source decisions,
pinned data and scope of exploratory permission stay unchanged.
Unverified mail delivery or lack of a reply is not permission.

## Architecture and boundaries

- Registry: fixed provider/source ID, versioned terms URL/digest and
  review date, allowed methods/HTTPS endpoints, explicit rights for
  fetch/retain/normalize/model fit/retain model/derived metrics, expiry,
  attribution, upstream restrictions, quota and budget. New source
  default DISCOVERY_ONLY; capabilities separately approved; fail closed.
- Bronze: private ignored directory, content-addressed immutable raw
  bytes, source and fetch receipt, source schema version, real local
  UTC receipt clock, response-size and hash. Store only when retention
  is permitted. Never publish raw data, secrets or local paths.
  Poll only approved endpoints; conditional request/cursor when
  supported; no change -> no duplicate bytes. Persist corrections as
  new observations rather than silently replace records.
- Silver: normalize typed provider rows; canonical player and edition
  crosswalk, singles main-draw scope and tier; provider match ID distinct
  from canonical ID. Exact match alias required; ambiguous matches,
  conflicts, wrong scope and missing dates are explicit quarantine.
  No fuzzy auto-merge, no majority vote, no fabricated round/surface.
  Preserve source-specific revisions and first seen provenance.
  Do not treat absent match in a partial export as a deletion or void.
- Gold: separate real-research database with its own schema marker and
  explicit mode, never relabel the synthetic DB or weaken its CHECK
  constraints. Adapt only after authorized schema/identity inspection.
  Cross-source reconciliation yields a canonical version with linked
  evidence; old versions remain immutable. A source or row may support
  historical research without qualifying for prospective scoring.
- Prediction: freeze actual fixture revision, features, model and
  cutoff before scheduled start; for prospective scoring require
  verified actual-start clock and result observation/availability
  conditions from binding S4/S5 policy. Date of event, scheduled
  start, first serve, provider publication and local receipt are
  distinct. A local first observation is not historical availability
  or authenticated actual start; missing remains unknown. Preserve
  28-day event maturity, no same-event leakage, reserved holdouts.
- Existing S7 worker lease/backup, pinned dependencies and dashboard
  are the integration points. Initially no automatic real job; manual
  bounded intake only after receipt. Never fetch or fit on UI rerun.
  Later owner-approved local scheduling respects power-off, quota,
  idempotency, retry backoff and stale states; no automatic promotion.

## Reuse audit

P1.5 implementation already exists at src/atp_gate/tml_snapshot.py,
tests/test_tml_snapshot.py and scripts/tml_daily_update.ps1. It is an
explicit local current-season updater with 24h default interval and
20 MiB cap, immutable SHA-qualified CSV and metadata index, source
schema checks and anomaly counts. Keep V3 files unchanged; reuse its
validated inputs only within new approved scope. Do not invoke its
force flag or daily script as a shortcut to S8 activation. A future V4
network boundary must independently test each redirect before following,
not rely on a post-response final-origin check. S3 adapter and current
schema are intentionally synthetic-only, not a ready real collector.

## Activation gates and acceptance

S8.0 design/terms inventory and synthetic contract tests; no network.
S8.1 offline replay, isolation, provenance and dedup tests with invented
fixtures, no real source bytes. Independent review and exact-head
owner approval before merge. S8.2 source-specific approval receipt
and signed owner scope; bounded manual dry run for one tournament,
up to 30 total requests including retries, up to 25 MB total, up to
2 requests/minute and 0 USD default. Any seasonal CSV exception requires
separate declared per-request/total cap (P1.5 cap is not V4 approval).
Record terms, redirects, clocks, coverage, anomalies and cost in local
evidence. If source/timing/identity insufficient, remain blocked.
S8.3 real parity and prospective evaluation protocol only after
separate approval; no training/export/scheduler/promotion without its
own gate. No changes to existing main or accepted research evidence
through this proposal. Independent source/rights/timing and design
review are still pending.
