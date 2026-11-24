# Paper-only calendar-period risk state (Issue #18)

**Scope:** ATP `paper_ledger` simulation and `policy.evaluate` input safety only. This is **not** a real-money staking engine, a profit guarantee, nor a verification of historical odds provenance. No source, model-training, or market-readiness gate is changed.

## Calendar contract

- All policy periods are calculated in `Asia/Bangkok`, from timezone-aware instants.
- `RiskState.selection_day` is a local `date`. A reservation increments `selections_today` for its accepted timestamp's local day.
- `RiskState.loss_week_start` is the **Monday date** beginning the local week. A `SETTLE_LOSS` increases `week_loss_realized` in the **settlement** week by the original `RESERVE.amount`, not by the settlement payout (which is 0 for a loss).
- An open position remains exposed across midnight and Monday; only settlement releases it.
- Weekly loss is **gross realized stake losses**, not net profit. A winning position does not offset previously realized weekly losses.
- Both fields may be `None` when decoding old snapshots, but `policy.evaluate` then returns `ABSTAIN` with `RISK_PERIOD_UNVERIFIED`.

## Correct paper-only caller order

1. Construct or load `PaperBook` with retained, complete, trusted journal and matching positions, risk balances and period counters.
2. Call `book = reconcile_periods(book, as_of)` **before** constructing a `DecisionInput` or calling `policy.evaluate`. This function validates journal chronological order, quote-independent reserve and settlement evidence, existing stamped counters, current positions, open exposure and seen match IDs.
3. Pass `book.risk` as `DecisionInput.risk`. A valid local period stamp is **necessary**, not by itself proof that the journal or model came from a trusted source. Model report validation, current odds authenticity and all other fail-closed gates still apply.
4. Use `record_selection(book, match_id, decision, odds, at)` only for an independently authorized hypothetical selection. It reconciles again at `at` and refuses duplicate match IDs, stale periods and all existing exposure caps. Journal entries and position maps are copied to the returned `PaperBook`.
5. Use `settle_selection(book, match_id, outcome, at)` only with a verified provider-mapped settlement. It reconciles first; the original stake is charged to the settlement week on a loss.
6. Call `close_month(book, next_month)` at the reporting boundary before entering any event belonging to the next Bangkok-local month. This preserves **unsettled** positions and journal history: the held stake is a **cost-basis asset**, not an assumed loss. The monthly report includes `carried_open_exposure`; it computes `net = free_cash + protected_cash + open_exposure − 1000` without valuing future outcomes. The next paper month begins with `free_cash = 1000 − open_exposure`, retains open positions, and resets realized-month counters. Actual WIN/LOSS/VOID is attributed to the **settlement month**. The `needed_topup` field remains externally replenished funds, not investment return.

No method accesses a clock implicitly; all boundary times come from explicit timestamp input. A source lacking the complete replay journal is **not eligible** for automatic repair; do not artificially reset daily/weekly counters to work around missing history.

## Integrity limits

- `replay_journal` proves **internal consistency** of the supplied events, not the authenticity, immutability or economic legitimacy of those events. Independent archival/signature and provider verification are separate requirements.
- `RiskState` is not digitally signed. A caller could supply a manipulated journal plus matching counters. This paper gate cannot independently detect that without a separately trusted journal source.
- Historical transactions recorded only in older counter-only records cannot be reconstructed. Unstamped nonempty legacy states must be quarantined or manually reviewed; no inferred reserve/settlement events.
- `close_month` can carry an unsettled paper stake across month boundaries at its original cost basis, but does **not** mark the position to market, certify external cash transfer, or verify an actual bookmaker settlement. A loss or win is recorded only when a supplied settlement outcome occurs in the current local month. The original placed-at time is retained; never backdate the settlement. Reject missing or conflicting journal evidence.
- The paper-only annual loss and profit-lock semantics remain unchanged; the capital reset at month close is already recorded as an external top-up in `MonthlyReport.needed_topup` and must not be mistaken for trading returns.
- Existing constants (`MIN_EV=0.02`, `MAX_STAKE=10`, `0.25` fractional Kelly and all other exposure limits) are research hypotheses, **not empirically validated optimal parameters**.
- ATP February 2024 incomplete/unverified match records, absent T−60 quotes and untrusted model evidence continue to require `ABSTAIN`; no selection may enter live wagering.

## Verification

- Tests: `python -m pytest -q`; particularly `tests/test_period_risk.py`, `tests/test_gate.py` and `tests/test_ledger.py`.
- CI: `ATP Lab CI` on Ubuntu/Windows, Python 3.11/3.12; every job must pass before a code merge.
- Process: [merged design PR #19](https://github.com/24021368-DucAnh/atp-forecasting-research/pull/19), [implementation issue #18](https://github.com/24021368-DucAnh/atp-forecasting-research/issues/18), [draft implementation PR #20](https://github.com/24021368-DucAnh/atp-forecasting-research/pull/20).

## P0.25a — Exact paper WIN payout checks (2026-11-24)

The accepted **paper** decimal odds and selected side are now recorded **at the original `RESERVE` journal event**, alongside stake and timezone-aware event time. They are not read back from a mutable `PaperPosition` after settlement.

- `replay_journal` checks every `SETTLE_WIN.amount == original RESERVE.amount × original RESERVE.odds` with exact `Decimal` arithmetic. A payout merely greater than stake is **not** sufficient.
- `reconcile_periods` checks that every currently open position's side and accepted odds match its original journal RESERVE evidence. LOSS remains zero payout, VOID exactly refunds original stake.
- Legacy journals without accepted odds may still be used to reconstruct manual LOSS/VOID daily/weekly period counts, but **cannot certify WIN settlement amounts or active position prices**. Never invent historical prices to backfill such evidence.
- Nonfinite odds (NaN / Infinity) and attempts to declare or change accepted odds on a settlement event are rejected during replay, even if a caller has used Pydantic `model_copy(update=...)` to bypass construction-time validation.
- The settlement payout currently uses exact `stake × odds` with **no bookmaker rounding**. If a licensed external sportsbook ever becomes relevant, its real market rounding, commission, taxes, retirement and void rules would need their own provider-specific independent reconciliation. None has been certified here.

**Important limit:** This internal journal replay is **not tamper-proof**: an adversary could rewrite both the original reserve and settlement amounts, or forge an entire consistent journal. In addition, `free_cash`, `protected_cash`, month-close external top-ups and year-to-date cash resets cannot be fully reconstructed from a uniquely authenticated opening balance and transfer ledger in the present schema. P0 Issue #25 remains **open** for its separate full cash and provenance stage, which will require explicit `OPENING_BALANCE`, `MONTH_CLOSE`, `TOPUP`, `TRANSFER` evidence and a migration policy. No real-money allocation or verified returns follow from these synthetic paper checks.

## P0.25b.1 — Complete synthetic cash history verification

The separate read-only module `atp_gate.paper_cash_history` verifies a complete
paper cash history without trusting the balance fields in the supplied
`PaperBook`. It does not modify legacy snapshots or the selection policy.

**Evidence contract**

- `OpeningEvidence(at, amount)`: 1 January at Bangkok local midnight,
  exactly 1000 synthetic units, zero existing positions. A midyear legacy
  snapshot is not a substitute for the missing preceding history.
- The original match journal: RESERVE must contain its accepted side and
  price; WIN/LOSS/VOID amounts must reconcile against that reserve.
- `MonthCloseEvidence` for each elapsed local calendar month: boundary,
  closed month, net result, cost-basis carry, ending unlocked and protected
  balance, explicitly simulated top-up and withdrawal. Preserve the returned
  `MonthlyReport` using `close_evidence_from_report(report, boundary)`.
  This helper records assertions, not proof that an actual transfer occurred.

Call `audit_cash_history(book, opening, closes, as_of, expected_sha256=anchor)`
with complete evidence, an aware explicit clock, and optionally a digest from
a separate trusted archive. It verifies every month boundary, internal cash
transfers, accepted payouts, open position identities, current risk-state
balances and period counters. At the exact month boundary the close precedes
new-month match events. December's closed deficit remains in December's
report and in cumulative simulated funding; the new calendar year's annual
negative-month counter starts at zero. A week straddling New Year retains its
own loss counter.

The cumulative paper result is:
`free_cash + protected_cash + open_exposure + simulated_withdrawals -
simulated_topups - opening.amount`. Open exposure is carried at original
cost, not a forecast of its value. Internal protection transfers cannot count
as external deposits or withdrawals.

**Digest semantics:** `cash_history_sha256` uses the versioned canonical
evidence (not the supplied end-state balance) with normalized UTC timestamps
and exact decimal value tokens. `anchor_matches=true` means only that the
supplied digest equals the evidence digest; the verifier always reports
`external_authenticity_verified=false`. A hash derived from an edited journal
is not proof of original provenance. Keep independently retained evidence and
never fabricate missing opening, monthly, price or funding records.

**Scope still open:** evidence capture and persistent append-only storage,
trusted external anchoring, and independent review/integration remain separate.
This verifier is not an API for payments or betting. All values are synthetic;
no actual profit, model edge, financial transaction, live allocation or
bookmaker settlement is certified.
