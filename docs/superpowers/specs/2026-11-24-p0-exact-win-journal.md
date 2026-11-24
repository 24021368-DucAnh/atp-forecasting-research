# P0.25a — Exact paper WIN settlement replay (2026-11-24)

**Goal:** A paper journal replay must independently verify each WIN payout from the stake and **accepted** decimal odds captured at RESERVE, not merely assert that payout exceeds stake. Open-position odds must agree with source journal evidence.

## Context and boundaries
- Existing `replay_journal()` checks chronology, duplicate reservation/settlement, LOSS=0 and VOID=stake, but WIN only `payout > stake`.
- Existing `record_selection()` stores odds in `PaperPosition` only, not `JournalEvent.RESERVE`. Altering a closed WIN payout currently evades its verification.
- Noncommercial/offline paper simulator; NO market evidence verification, training release or real-money API.
- Legacy manual RESERVE records may omit accepted odds. They may still replay historical LOSS/VOID **period counts**; never qualify for independently verified WIN payout. An open position with no journal accepted-odds evidence must fail `reconcile_periods`.
- **Explicit non-goal for 25a:** complete cash balance, external funding/annual transfer replay, journal provenance/authenticity. Those require a distinct versioned ledger migration (25b), including opening-equity and rollover event contracts. Do not claim #25 globally closed by this PR.

## Interface
- `JournalEvent` gains optional `side: Literal['A','B'] | None` and `odds: Decimal | None`. Only RESERVE may carry them, and new RESERVE via `record_selection` always records both. Optional on manually constructed legacy RESERVE for backward compatibility.
- `PeriodReplay` gains `reserve_odds: dict[str, Decimal]` and `reserve_sides: dict[str, Literal['A','B']]` (for active and settled reservations).
- On WIN, reject missing accepted odds; require EXACT Decimal payout == reserve amount * accepted decimal odds. Same Decimal multiplication convention as current `settle_selection`; no unsolicited integer rounding.
- On open position reconciliation require `PaperPosition.side`, `PaperPosition.odds`, `stake`, `placed_at` equal accepted journal details, preventing state-level odds tampering.
- Reject nonfinite event amount/odds and nonfinite odds passed to `record_selection` (including `NaN`, `Infinity`); all must be valid Decimal values before arithmetic.
- A rewritten RESERVE and matching forged settlement remains undetectable *without* externally authenticated immutable evidence. Report this explicitly; no false tamper-proof claim.

## Verification
- RED: replay accepts fake WIN amount 20 on RESERVE stake 10 and accepted odds 1.90 (correct payout 19); this must FAIL. Forged open position odds must FAIL. Missing odds for WIN must fail. Legacy LOSS/VOID period replay still works.
- GREEN: full 4-job GitHub CI on stacked PR targeting integration branch. No changes to `policy.evaluate` or `allocation_enabled` behavior.
