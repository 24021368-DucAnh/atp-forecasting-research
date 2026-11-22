# ATP Selective Forecasting — Input Gate Design (V0.1)

## Intent

Create a trustworthy input boundary in front of a pre-existing ATP tennis XGBoost/Elo engine so that invalid sports data, future information, mislabeled odds, self-certified models, and misaccounted bankrolls do not silently affect selection. Build the smallest working component first, offline and paper-only.

## Goals

1. Validate the exact selected competition, match identity, confirmed start time and as-of timestamps.
2. Enforce the upstream model's 18-feature schema, missingness and surface consistency.
3. Disallow any selection on stale, future, misleading or unmatched prices.
4. Refuse any model without separately allowlisted validation-report evidence.
5. Apply a deterministic research allocation rule and defend a protected cash ledger.
6. Reject historical CSV as live T−60 odds even when it includes opening/closing prices.
7. Implement tests for the critical failure classes and a CLI/JSON contract.

## Non-goals

- Producing verified model probabilities or demonstrating profitability at this stage.
- Executing financial transactions, collecting sportsbook accounts or placing bets.
- Choosing the optimal thresholds before a multi-season untouched backtest.
- Building the full dashboard, ingestion scheduler, model-training environment, or live quote adapter in this iteration.

## Alternatives considered

- **Fork the complete ATP Value Board:** feature-rich but source-code reuse permissions not confirmed; hard to independently audit the entire pipeline. Rejected for first implementation.
- **Build a model from zero:** wastes the upstream project's Elo, XGBoost and comparison components; delays leakage checks. Rejected.
- **Use a separate, strict input/decision gate with a pinned MIT upstream model:** allows testing and repair of the most consequential boundary before ML integration, without copying upstream code. **Selected.**

## Architecture

```
licensed fixture/odds feeds (not yet integrated)
         |
stable source/player/match identity resolver (not yet integrated)
         |
point-in-time pre-match feature adapter (not yet integrated)
         |                 pinned coenensam/Elo/XGBoost (not yet integrated)
         +-----------------------------+
                                       v
       pydantic DecisionInput + feature schema + provenance report allowlist
                                       |
                              fail-closed evaluate()
                                       |
                         SELECT (paper) / ABSTAIN
                                       |
                            PaperBook event journal
```

### Exact interfaces delivered

- `DecisionInput`: six namespaces, including as-of time; Pydantic AwareDatetime/extra-forbid.
- `evaluate(data, trusted_validation_reports=...) -> DecisionOutput`.
- `apply_profit_lock(risk) -> (risk, transfer)`.
- `record_selection(book, match_id, decision, decimal_odds, at) -> PaperBook`.
- `settle_selection(book, match_id, outcome, at) -> PaperBook`.
- `close_month(book, next_month) -> (PaperBook, MonthlyReport)`.
- `audit_tennis_data_csv(path) -> dict` (research-quality only).

## Constraints and risk rules

- All timestamps timezone-aware. Reporting month and day calendar in Asia/Bangkok. Any market pricing timestamp > decision time is invalid.
- Match format per competition: Grand Slam BO5, Masters 1000 BO3, ATP500 BO3, men's singles main draw only.
- Model score must follow feature snapshot, independently validated model report, and real as-of data.
- No imported results fields as features; all data with unknown critical provenance is quarantined.
- X=1000 paper units/month; fractional Kelly 0.25 with a 1% X per-selection cap; 2% X concurrent exposure cap; weekly gross loss limit 3% X; minimum +2% conservative EV (hypothesis); weekly and annual caps.
- Profit lock at wallet >=1050 and exposure zero protects 1040, leaving surplus for restricted paper simulation; track actual profit as `protected + unlocked - X`.

## Design review findings

- External model code builds approximate match dates; do not use that signal to certify true intra-tournament pre-match features.
- Model uses rank information during training but hardcodes rank difference to 0 when inferring; reject such imputation.
- Fuzzy odds match tolerance is too broad for safe T−60 price use; demand verified one-to-one matching.
- The earlier exploratory four-month ATP tests do not demonstrate profitability; zero model validation by default.

## Completion and acceptance

Acceptance for V0.1 = all input rejection and paper-ledger tests pass, CLI returns `ABSTAIN` for synthetic unvalidated model, historical CSV cannot be marked T−60-eligible, and a distributable zip is created. The next design milestone is a point-in-time source adapter and independent evaluation pipeline.
