# P3A — T−60 Quote Receipt Preflight (Paper Only)

The `quote_receipt.py` helper checks a **claimed** provider-observed prematch quote against explicit fixture identity, schedule, retrospective actual first serve and an independently provided receipt-review digest.

It never scrapes a bookmaker, opens a wager, assumes odds at another time, certifies a source's legal rights, proves model advantage, or approves financial allocation.

## Inputs and function

```python
from atp_gate.quote_receipt import audit_quote_receipt

report = audit_quote_receipt(
    snapshot, as_of=decision_datetime,
    trusted_receipts={},  # empty = NO_TRUSTED_T60_SOURCE
)
```

Use timestamp-aware `as_of`. The snapshot requires exactly three objects:

- `fixture`: stable match and ordered player A/B identifiers, a confirmed scheduled start instant, retrospective actual first serve (or `null`), and status (`SCHEDULED`/`DELAYED` accepted).
- `quote`: same match and ordered players, bookmaker, quote ID, HTTPS source URL, MATCH_WINNER market, both decimal offered odds strings, published/observed/retrieved instants, market status `ACTIVE`, retirement settlement rule `RETIREMENT_ACTION` or `RETIREMENT_VOID`.
- `receipt`: report ID, content SHA-256 and rights-review marker. The caller must separately manage a trusted, immutable provider receipt registry. A self-declared report hash without such trusted registry does not establish any trading evidence.

## Time checks

1. `published_at <= observed_at <= retrieved_at <= as_of` and quote age no more than 30 minutes.
2. The decision instant must be at least 60 minutes before **confirmed scheduled start**; after the match, if true first-serve timestamp is available, verify it separately against the same cutoff.
3. Unknown actual first serve is a separate failure, not something inferred from tournament start date or round ordinal.
4. A suspended or revoked market is not an active offer. Both players and same market must line up with the verified fixture.
5. Suspicious overround or unknown retirement/void rule requires rejection.

**Retrospective audit caveat:** actual first serve occurs in the future relative to a prematch decision. It must NEVER be used in computing that prematch prediction or in a contemporaneous selection rule; use it only for later audit. The helper is not the existing live policy's adapter.

## Output and guards

- `QUOTE_REJECTED`: data contradicts identity, schedule, price, cutoff, suspension or settlement conditions. Reasons list explains why.
- `NO_TRUSTED_T60_SOURCE`: mechanical checks pass but no matching independent receipt review exists.
- `QUOTE_REVIEW_ONLY`: both mechanical checks and an independently supplied report ID+SHA match, still **not** verified executable market price or reliable value.
- Always `t60_execution_verified=false`, `market_edge_verified=false`, `allocation_enabled=false`, `stake=0`.

A trusted *report digest* proves only that the caller references the reviewed report if the registry is independently protected. It is not a signature from a bookmaker and does not prove quote availability or the right to redistribute odds.

## Missing real evidence

Issue [#13](https://github.com/24021368-DucAnh/atp-forecasting-research/issues/13) remains open pending a legitimate provider offering a legal, verifiably timestamped market and actual/scheduled first-serve records. Historical opening and closing odds may be used only for retrospective comparison; neither can be renamed to a T−60 price. P1.4d source rights, P2 out-of-time validation and P0 financial integrity remain independent blockers.

Only synthetic quote cases are committed in the test suite. No real sportsbook API connection is present.
