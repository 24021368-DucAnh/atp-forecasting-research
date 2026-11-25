# P1.8b — content-pinned duplicate sensitivity

Base bf59c2f4; P1.8a final CI 45455380000 passed. Issue #29, stacked draft #37.
The previous audit found exact-clone candidates in 2021 (2) and 2022 (1) and a conflicting-stat candidate group in original 2025 (1), absent from revised 2025. Keep 2024 and the level-A normalization unchanged.

Ruling: implement a research-only derived-byte transformation separate from the Elo loader. Pin every input season's SHA256 and expected counts of exact/conflicting main-tour groups; reject mixed scope or ambiguous/missing numeric identities in a candidate group. Use event/round/unordered player IDs to detect groups, compare all other columns except match_num for exact clones. Keep the lowest numeric match_num only as a deterministic local representative, never claim it is the official ID. Preserve no-change bytes and malformed rows; derived bytes are temporary and receive their own SHA256. No source data committed.

Three scenarios: locked normalized baseline (A), exact clone collapse (B), plus quarantine all conflicting group rows (C). For both original and revised pinned sets, reconcile eligible counts, folds, aggregate scores, and matched evaluation multiset under unchanged 28-day Elo timeline; no selection/tuning. A conflicting group stays unchanged in B, never pick a conflicting stat row. External result corroboration does not verify official match identity. Candidate group scope excludes special formats and does not allow mixed-scope modifications. No certified training, allocation, or market claims.

Acceptance: test-first RED then GREEN and full suite, real-source Python results with source and derived hashes, ledger and independent review before merge. No main merge.
