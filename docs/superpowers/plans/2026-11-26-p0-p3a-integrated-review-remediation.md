# P0/P3A integrated review remediation

Base 4208fac3761f89c72700295907ea1b96424e9b99; owner-supplied independent review WITH FIXES: 0 Critical, 2 Important, 4 Minor. Issues #18, #21, #25, #13. Main-push CI 45757248737: 630 tests and 260 manifest entries x4; coordinator verified raw logs. #21 and #25 YES subject to shared fixes; #18 and P3A WITH FIXES. Review scope synthetic-only.

## Narrow contract
- IMP-1: replay rejects PROFIT_LOCK if any open stakes remain, even if settlement ID/time/amount match; cash threshold validation remains the independent cash audit's responsibility.
- IMP-2: reject leading/trailing whitespace in nonempty identifiers/text validated by quote preflight; do not silently normalize identities or change matching semantics.
- MIN-3: reject blank/padded journal IDs at replay and reservation entry, including mutated evidence; no normalization of old evidence.
- MIN-4: cash audit report adds policy_compliance_verified=false; archive inherits it without changing persisted envelope/digest schema. Cash arithmetic does not certify policy compliance.
- MIN-1: preserve preregistered observed-time freshness (30 minutes). Old published time with recent observation may pass mechanical review only; no execution claim. Do not change age threshold absent a separate protocol decision.
- MIN-2: report ID/hash lookup is an equality check on a public evidence identifier, not secret authentication or payload binding. HTTPS URL is syntax-only, no network request; localhost may occur in synthetic input. Do not certify source rights or introduce unregistered network allowlists. Real provider/source trust remains blocked.

No real data, holdout, financial activity, policy-threshold changes, market/source acquisition, or historical evidence edits. All safety flags preserved.
- [x] Verify findings and register regression contracts.
- [ ] Observe intended RED with canonical manifest verified.
- [ ] Implement narrow fixes and verify full matrix GREEN.
- [ ] Independent review and explicit owner approval before merge; verify push CI.
