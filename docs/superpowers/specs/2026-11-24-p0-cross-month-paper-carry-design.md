# P0 Cross-Month Paper Position Carry — Design (2026-11-24)
**Issue:** #21. **Dependency:** Draft implementation #20; this branch is stacked on its test-verified head `8a745dd`. **Mode:** PAPER ONLY.

## Intent and actual source of defect
`record_selection` moves stake from `free_cash` to `open_exposure`, and `settle_selection` realizes its economic gain or loss. The old `close_month` rejects outstanding positions; `reconcile_periods` then rejects settlement in a month different from `RiskState.month`. A match crossing local midnight cannot be accounted for without backdating or non-audited workarounds.

## Approaches
1. **Delay month close until last position settles:** cannot generate an immutable closing snapshot on the month boundary, silently changes period attribution; reject.
2. **Mark open bets at an estimated market price:** requires independent observable market prices at month end and introduces unrealized P&L to a no-market-source paper-only ledger; reject.
3. **Carry open stake as a cost-basis asset; recognize return on settlement date (chosen):** deterministic, auditable under the paper book's existing cost-basis accounting. Report realized-period net at cost, not mark-to-market; preserve exposure, the original position, and event timestamps.

## Precise boundary mechanics
At local month close with `F=free_cash`, `P=protected_cash`, `O=open_exposure`, and reference `X=1000`:
- `report.net = F + P + O - X`; open position is carried **at original stake cost**, with no assumption of win/loss/fair value. This remains the month P&L for settled outcomes when the book was funded to X at the prior close.
- `report.carried_open_exposure = O`, `report.ending_unlocked = F`, `report.protected=P`, `report.needed_topup=max(-net,0)`.
- Transfer an **externally funded** net-equity reset to new period `F_next=X-O`, `O_next=O`, `P_next=0`; copy open positions and journal, preserve original `placed_at` and its odds.
- Reset current-month reserve IDs and monthly gross-loss amount; recompute daily/weekly counters at the next month's Bangkok midnight using intact journal. Persist annual loss accumulation from negative **recognized** prior-month net; December-to-January resets year negative-month-loss counter before adding any next-year settled loss.
- On next-month settlement, `SETTLE_WIN` adds stake×decimal_odds to free cash, `SETTLE_VOID` returns exactly the reserved stake, `SETTLE_LOSS` adds zero, and `open_exposure` drops by stake. This credits realized win/loss only in its settlement month; prior-month pending stakes never count as loss.
- Validate journal and position/exposure identity at cutoff before any transition. A journal event on/after the next month's boundary (or an earlier dated settlement after month close) must fail. Reject open exposure over X and nonfinite/non-decimal values.
- No transfer of old `seen_match_ids` into the new month. Global duplicate match IDs remain guarded by the retained journal.
- The close outcome is a **paper research-unit accounting statement**, not an audited bank cash flow or tax-grade accrual. Any replenishment amount remains an external transfer; `needed_topup` must not be misreported as return.
- No odds retrofitting, live execution, external provider rights or changes to existing P0 risk limits. Raw data and T−60 remain blocked.

## Hard non-goals
No method for changing bookmaker settlement conventions; no mark-to-market, future outcome inference, account integration, claims of profit or audited transaction completeness. No modification of model gate, Kelly fraction or allowed competitions.

## Acceptance
TDD tests for: reservation Jan 31 23:50 local and settlement Feb 1 00:10 local as WIN/LOSS/VOID; two pending matches; annual Dec/Jan boundary; concurrent weekly carry across month; journal preserved, matched exposure, no backdating, negative cash refused. Full pytest and four CI jobs green. Draft PR remains unmerged until independent review.
