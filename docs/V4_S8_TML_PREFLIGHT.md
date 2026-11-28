# V4 S8.2 — TML historical-only preflight (RallyForge AI)

Status: implementation for review; no real-data activation.

## Scope and evidence
Owner clarified on 2026-11-28 that RallyForge AI is personal, private,
educational and noncommercial, for experimentation with AI/ML. The public
TennisMyLife data usage terms themselves are written evidence of the
permissions expressly granted by the publisher. A separate email is not
automatically required where the terms already establish the applicable
permission. This is not a claim of independent upstream clearance, a new
permission receipt, or approval for any activity not expressly allowed.

Reviewed official sources:
- https://stats.tennismylife.org/tennis-match-database (CSV download
  instructions, column descriptions, tournament week, separate ATP
  qualifying files, ongoing results, terms).
- https://tennismylife.github.io/TML-Database/ (personal, educational,
  noncommercial research; raw redistribution not authorized; restrictions
  or permissions of third parties may apply).
The public terms cover only rights the publisher is entitled to grant.
Preserve attribution, local/private operation and source restrictions;
no commercial service, monetization or raw redistribution. If a specific
right or upstream restriction is uncertain or conflicts with intended use,
resolve it before that operation. No reply to an email is not permission.
No source data or credentials are committed to the public repository.
This scope interpretation does not override the binding V4 design or the
S8.2 source-specific receipt and exact owner dry-run approval gate.

## Offline adapter
Reuse P1.5 TML_COLUMNS, MAX_BYTES and _check_csv without changes to V3.
atp_lab.intake.tml_preflight.inspect_snapshot inspects bounded caller-
supplied bytes against exact SHA256, season, one provider event ID and
a UTC inspection time. The reported inspection time is NOT an actual
source observation time. Returned rows are unverified historical candidates;
provider keys are not canonical identity, level A is not an official tier,
score shape is not verified match completion, and tourney_date is only
the tournament week. Candidate rows with multiple weeks fail closed.
Missing actual start, publication and historical availability remain null.
Reports cannot enable training or scoring via their constructors.

compare_snapshots compares two inspections for the same event and season.
It distinguishes unchanged rows, new rows, changed raw-row digests, changed
player identity/week, quarantined rows, recovery from quarantine and rows
not observed in the later export. Not observed is never a deletion, void
or correction. This is provider-local comparison, not cross-provider
canonical reconciliation. A caller must retain the immutable input
snapshots; no database writes, downloads or network transport are included.
The output is an audit helper, not trusted authorization or a model input.
Historical score syntax is only a candidate screen; independent canonical
identity, tier, outcome/coverage and actual-start review remain separate.

## TDD evidence and limitations
Base main 397160dc6c3bf7f9f08fc484977e74d81bd04c0c, accepted S8.0/S8.1.
Local git DNS unavailable. Isolated workspace Python 3.13.5 used exact
P1.5 _check_csv and TML_COLUMNS excerpts verified byte-for-byte (plus
MAX_BYTES=20 MiB). No real payload. 23 tests RED (missing module), 23
GREEN; self-review added three cases (mixed event weeks, constructor
override, recovery from quarantine), 2 expected failures/24 pass; fixed
both failures, accounted for Python-version-specific dataclasses.replace
exception, final focused 26/26 pass. Full repository CI required separately
on Windows/Ubuntu Python 3.11/3.12 plus UI. Author self-review only.
No independent review or stage-specific waiver assumed.

## Next
Prefer an already-held, hash-qualified, lawfully obtained TML snapshot
for a one-event local audit after source-specific scope/rights approval.
The current adapter has no live fetch; if a new fetch is needed, design
the bounded fixed HTTPS transport, reject redirects before following,
and obtain exact scope/byte/time/attempt authorization. A successful
historical audit does not certify prospective timing or unlock real
training. 2026 was previously exposed and is not an untouched holdout.
S8.2 remains partially implemented; real dry run, actual source identity/
rights review, independent timing/fixture source, and S8.3 remain gated.
