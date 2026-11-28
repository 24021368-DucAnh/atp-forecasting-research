# V4 S8.2 - Historical outcome inventory (review only)

Base: e22c89fa175385af07bb8364fbf92ca80132603f, PR #78 accepted.
Issue #75. The earlier owner-local Rotterdam replay reported 31 observed
rows and 31 provisional links per source, 30 completed agreements and one
retirement in quarantine. The completed-result draw audit correctly flags
its incomplete candidate inventory. It must not be weakened to pass it.

## Contract

`atp_lab.intake.outcome_inventory.audit_inventory` is a separate, pure
comparison of two caller-normalized, hash-qualified inventories. Supply
reviewed source editions, raw provider level for each, tier, surface,
event window, explicit best-of format and expected round counts. Supply
source-local match/player IDs, row digest, declared outcome and normalized
winner-first score, optional individual calendar date, explicit one-to-one
match and player links. The input claims and digests are not authentication
of raw bytes, verified canonical identities, rights or independence.
The accepted preflight and completed-result audit APIs remain unchanged.
The new module is not a CSV parser, transport, warehouse or model input.

Report observed raw round inventory completeness separately from linked
outcome agreement. Count completed agreements, retired/walkover/void
agreements and unresolved expected slots (deficit by round, so surplus in
one round cannot fill another). Report every comparison decision count,
unlinked counts, unexpected/missing rows, repeated player within a round,
metadata, player, winner, round, status, score and supplied day conflicts.
Round count agreement is not certification of official bracket progression
or actual draw completeness. Full inventory agreement still requires review.
Unknown outcomes never agree. VOID is only an explicit VOID with no winner;
W/O requires a stated winner and no games; RET requires a plausible played
but unfinished match. Scores are conservative modern conventional tiebreak
sets with an optional tiebreak annotation. Extra sets after either player
clinches, impossible sets, contradictory status/score and unsupported
formats require review. The declared best-of is checked; no inference from
score or tier. Exact score comparison normalizes whitespace only. A
retired winner is not necessarily ahead at retirement. No result is made
eligible; non-completed agreement is corroboration of the description only.

Unknown left/reference match dates remain unknown and are reported
separately; neither dates nor tournament week prove actual first serve or
publication. The deterministic digest binds all normalized inputs and
explicit links, not raw provider bytes. Output exposes only aggregate
counts, finding/decision codes and digest. No data writes, downloads,
real receipts, raw data, training, scoring, scheduler or import.

## Evidence and limits

39 fictional tests failed first (missing module), then 39 passed. A separate
author review added 3 regression cases for agreement outside the expected
round, extra agreement masking a missing round, and missing dates on the
left only. All 3 failed for their intended reasons before correction.
Final isolated suite: 42 passed, Python 3.13.5, py_compile clean. The
container cannot resolve github.com for a full checkout; full repo CI is
required, and no independent reviewer was available. Preserve all 365
accepted manifest pins; add only this module, tests and documentation.

Ruling: add an independent normalized inventory report rather than change
accepted completed-result audit semantics. The next adapter must bind
normalized rows to the existing verified private snapshots and reviewed
scope. If this interpretation is wrong, the new report could be misread
as official bracket certification; explicit review-only flags, unchanged
old audit and documented limitations prevent activation. No real replay
of the new module performed yet. Use existing private cache only after
exact-head acceptance; no new source GET or new receipt. Rights, upstream
lineage, canonical identity, actual start and publication remain separate
blockers. S8.3 remains locked.
