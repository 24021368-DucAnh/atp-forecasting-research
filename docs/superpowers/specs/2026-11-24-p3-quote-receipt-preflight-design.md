# P3A — Independent T−60 Quote Receipt Preflight (2026-11-24)

**Issue:** #13; **status:** paper-only source preflight, not betting execution.

## Goal
Stop using untrusted historical closing/opening odds as if observed at a true pre-match decision time. Define and test a strict one-quote receipt for provider timestamp, fixture start and identity alignment, suspension, cancellation and retirement rules. Even a structurally valid receipt is not an executable price without an independently trusted provider receipt and market evidence.

## Approaches
1. Re-label closing historical odds as T−60: rejected as fabricated timing.
2. Infer first serve by tournament date plus round sequence: rejected as fabricated time.
3. **Selected:** require independently observed quote timestamps and explicit fixture timing/IDs; audit source receipt under an externally controlled trusted hash registry; always report paper-only and never certify profitability or live stake.

## Input contract
`audit_quote_receipt(snapshot: dict, *, as_of: datetime, trusted_receipts: Mapping[str,str] | None = None) -> dict`.
Snapshot has:
- `fixture`: match ID, player A/B stable IDs, schedule start timezone-aware, `start_confirmed` bool, optionally `actual_first_serve` (timezone-aware or null), match status SCHEDULED/DELAYED/STARTED/COMPLETED/CANCELLED.
- `quote`: match and player IDs matching fixture in same order, quote ID, bookmaker, provider URL, market MATCH_WINNER, decimal odds as strings, published/observed/retrieved at time, market_status ACTIVE/SUSPENDED/REVOKED, retirement_rule ACTION/VOID/UNKNOWN.
- `receipt`: separately managed reference ID and SHA-256 for independent observed-provider evidence, source-rights-review status boolean (not enough on its own).
Strict no guessed missing fields; no outcome or quote after decision. Identity/order and temporal input failures reject. The mechanical rule is at least 60 minutes before confirmed scheduled start, quote age <=30 min, provider publish<=observe<=retrieve<=as_of, market active, known settlement, overround in plausible band. If actual first serve is known after match, separately require decision is at least 60 minutes before it; if not known, report actual-start evidence missing and no quote certification. Receipt trust requires exact matching independent ID→hash map, not self-assertion. Do not allow live allocation under any circumstances.

## Output
`status` one of `NO_TRUSTED_T60_SOURCE`, `QUOTE_REVIEW_ONLY`, `QUOTE_REJECTED`, `mode=HISTORICAL_RESEARCH_ONLY`, reasons sorted unique, `observed_quote_mechanics_ok` boolean, `independent_receipt_matched` boolean. Always `t60_execution_verified=false`, `market_edge_verified=false`, `allocation_enabled=false`, `stake=0`. Exclude future price and unobserved quote whenever receipt missing.

## Tests
Synthetic valid timestamp/no receipt, exact trusted receipt still no execution; mismatch player order, stale/future quote, cancelled fixture/suspended market, unknown retirement, unconfirmed/unknown actual start, observed quote within 60 min cutoff, fake source report and out-of-range odds. 4/4 CI; no third-party quote records committed.

## Non-goals
No odds scraping, bookmaker API actions, claiming offering price availability or accepting model training. No probability model, CLV or staking optimization.
