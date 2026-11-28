# V4 S8.2 - Numeric provider tier compatibility

This is a read-only audit correction, not a source activation. TML historical
snapshots can use numeric provider levels 250 and 500 as well as legacy A.
Keep the original provider level and row digest; only the separately
reviewed event scope establishes the official tier. The draw audit permits
250 only for ATP_250 and 500 only for ATP_500; A remains compatible with
both reviewed scopes, not evidence of either tier on its own. Unknown
levels, incompatible tiers and non-completed results remain quarantined.
No change to V3, network, storage, training or import permission.

## Real historical dry-run evidence (owner-local, 2026-11-28)

Issue #75 records the scoped recovery and offline candidate execution.
Both exact 2024 blobs were retrieved in two successful bounded requests
(1,796,135 accounted response-body bytes, USD 0), verified against Git
object IDs, and retained outside the repository. TML matches the V3 pin;
Sackmann digest is separately recorded in the tracker. The owner then
ran the offline candidate with exactly the two source module versions
in this change, a scoped private reader and the verified local cache.
The candidate reported 76 focused tests passed on Windows, zero HTTP
requests, 3,076 source rows per feed, 31 Rotterdam rows per feed,
31/31 provisional name-and-round links, matching winners and score text,
30 completed agreements and one retirement in outcome quarantine.
The observed level codes were TML 500 and Sackmann A. Expected rounds
were R32 16, R16 8, QF 4, SF 2, F 1; both raw inventories matched.
The audit digest was
4a48c75f1ff8db9142f66a0002cc421814a2df6df668d0f01f589e90b32a72a4.

The draw result remains CONFLICT_REVIEW_REQUIRED because the retirement
is excluded from completed candidates, producing a coverage finding.
This is not a missing raw match or evidence that the retirement should
be silently accepted as completed. Source independence, canonical player
IDs, actual start and publication/availability remain unverified. No row
is eligible for import, scoring or training. No vendor rows or private
source payloads are included here. The private scoped launcher is not
shipped as a general-purpose provider adapter or transport in this PR.

## Verification and remaining gate

At accepted base 379b5e10a8dec27f94fe0c4813eaba74240a5129, isolated
Python 3.13.5 verification of the exact two changed modules and original
legacy CSV modules plus the two accepted test files: 13 new fictional
regression cases, RED 5 failed / 65 passed, GREEN 70 passed (57 existing
and 13 new). The changed module hashes match the owner-local candidate.
Local full checkout was unavailable because of DNS, so full repository
Windows/Ubuntu CI and independent review (or exact-head owner waiver)
remain required before merge. Preserve the accepted manifest pins apart
from the two intentionally corrected modules and new files. Do not
infer real-data activation from either a green CI or a historical audit.
