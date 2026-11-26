# P2.5 synthetic commitment V2 follow-up (#57)

Base 5ed6bdc2ff23af1104910738e6995aa5438cc083. Owner-supplied independent acceptance YES for A2/A3 at this exact base: 0 Critical, 0 Important, 3 non-blocking Minor. Scope remains synthetic-only, no real data, network acquisition, holdout, model export or production. Do not alter historical registries, source evidence, or original review artifacts. V1 acceptance is preserved at its reviewed commit.

## Prior execution receipts (MIN-3)
- A2 RED 45646802112: 41 intended failures / 530 existing passes; GREEN 45647479500: 571 passes and 257 manifest entries on each of four jobs. PR #55 merged externally at 1972e394 before independent acceptance.
- A3 RED 45750744441: 49 intended failures / 571 existing passes; GREEN 45751050405: 620 passes and 259 manifest entries on each of four jobs. PR #56 merged externally at 5ed6bdc2 before independent acceptance.
- Combined independent review YES supplied after merges; main tree equals tested A3 head 9396da17; seven-file diff +537/-0 from 3b52a7d0. Receipt issue #54 comment 7182303066. No retroactive review-before-merge PASS. Original plan preserved as historical registration; this ledger records completed actions.
- Main-push CI receipt and owner acceptance of process exception still pending (#51 and subsequent merges). Required reviews/checks must be configured by owner; do not edit repository settings. No merge until independent review and explicit integration approval.

## Narrow V2 contract (MIN-1 and MIN-2)
The existing synthetic session API signatures stay unchanged. Version frozen state schema to SYNTHETIC_TWO_BIN_V2; after existing validation normalize feature values to 0.0 when equal to zero, otherwise float(value). Preserve distinct nonzero feature values, training keys, labels, request and probabilities in the frozen commitment. Prior V1 digests are not migrated or declared interchangeable. No persisted model artifacts exist in this demonstration.
After successful prediction, commit SHA256 of canonical JSON with schema SYNTHETIC_PREDICTIONS_V2, frozen_digest and exact key-to-probability map. Recompute before scoring; any mismatch or invalid serialization fails closed without consuming release. Aggregate report adds commitment_schema, frozen_digest, prediction_digest, retains all original safety flags and metrics. Prediction digest binds predictions, not raw matchup features; no authenticated custody or protection against arbitrary simultaneous private-state edits. One-time enforcement remains per in-memory session.
- [x] Verify review against source and register V2 contract.
- [ ] Observe intentional RED for mutation detection, provenance and numeric equivalence with manifest verified.
- [ ] Implement minimal V2 changes, run full GREEN 4/4, record exact HEAD and logs.
- [ ] Independent follow-up review and explicit integration authorization; do not merge RED.
