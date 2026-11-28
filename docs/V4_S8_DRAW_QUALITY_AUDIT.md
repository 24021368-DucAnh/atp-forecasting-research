# V4 S8.2 - Historical draw quality audit (read-only)

Part of issue #75. Owner requires exact cross-check before import.
This implements an offline audit, not a real importer or activation.

## Input and boundary

Reuse accepted S8.2 inspect_snapshot and its P1.5 CSV validator. Supply
one hash-qualified TML SnapshotInspection, an explicitly reviewed DrawScope
(event IDs, reference source, week/end day, ATP tier, surface, expected
round inventory), a normalized ReferenceDraw, one-to-one MatchLink and
PlayerLink tuples, and a lineage declaration with evidence hash if known.
All reference scores must already use winner-first notation. No guessed
provider columns, fuzzy name joins, automatic canonical identity or tier
inference. The caller must preserve both immutable original snapshots and
verify their normalization, source and rights separately. The supplied
reference hashes, alias mappings, expected draw and lineage evidence are
claims, not authenticated receipts. No actual provider-specific reference
adapter is implemented here.

The audit checks per mapped match: participant IDs and winner, round,
score, completed status, source-level/tier mapping, surface and event
week, optional reference calendar day in the event window. It also
checks duplicate identities/links, repeated player within an elimination
round, expected versus observed round counts, missing and unlinked rows,
and TML quarantine. Score plausibility is conservative conventional set
notation, not official match-format/best-of or rulebook certification.
Nonstandard scores and non-completed outcomes need separate review.
Expected coverage is relative to the supplied reviewed inventory; matching
partial feeds cannot establish complete official draw coverage.
Agreement is descriptive and always review-required; declared shared or
unknown lineage remains separately flagged. Missing day stays missing,
tournament week never becomes match time. No actual first serve or
publication/availability clock inferred. An audit digest binds normalized
inputs, links, source hashes and lineage declaration; it does not
authenticate provider bytes. No database writes, network, fit, scheduler,
model eligibility or import permission. Even full agreement cannot
authorize any of those. Audit reports are local; no vendor rows in Git.

## Source decision

Do not count TML and Sackmann as independent verification: the existing
src/atp_gate/tml_sackmann_crosscheck.py explicitly warns of shared lineage.
The old Valuebetennis pinned 2024 export lacked February UTC-dated rows
(docs/DATA_SOURCE_DECISIONS.md), so cannot establish Rotterdam coverage.
A different current export must be separately verified, not assumed fixed.
Rotterdam 2024 (provider event 2024-407, expected 31 rows per existing
TML crosswalk) is still a proposed zero-network audit scope from issue #75.
No actual source files in this environment; do not replace missing data
with a network fetch or an invented crosswalk. Independently sourced
reference evidence, scope/rights qualification and locally authorized
dry-run execution remain prerequisites. Verified source agreement does
not substitute for independent timing or prospective eligibility.

## TDD and review evidence

Base 7e1852c0637bbd6b9a59eec02a4ee148ab59eada. Git clone DNS unavailable.
Copied prior isolated S8 workspace; all nine accepted intake code/test
file SHA256s compared with main manifest. Baseline 78 tests pass.
Python 3.13.5 local: 26 RED (missing module), 26 GREEN; self-review RED
5 failed/26 passed (equal implausible score and repeated player in a round),
then 31 GREEN; combined focused suite 109 passed. Exact two new code/test
hashes verified before connector publication. No claim of full local
checkout, full regression or real-source validation. Full Windows/Ubuntu
CI needed; author self-review only. New PR requires its own exact-head
review/waiver and approval. No change to accepted S1-S8.1 or TML preflight.

Ruling: use a source-neutral normalized reference projection rather than
guess Valuebetennis or another provider's unverified raw schema. This
adds usable pre-import comparison but defers provider parsing/byte-binding.
Ruling: separate declared source lineage from actual independence, and
result agreement from import permission. Even a caller-declared reviewed
distinct lineage remains unverified by code.
Ruling: ordinary single-elimination draw scope only; exclude ATP Finals,
qualifying, doubles and nonstandard format cases. More formats require
their own evidence and contract. No real data accessed; no wider scope
or algorithm work. Adaptive Selective Forecasting remains after S8.
