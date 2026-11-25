# P1.9b parser remediation ledger

Main 97b36557, recovery #39 merged by external actor; main CI 45543006630 4/4 passed (411 tests). Earlier RED PR #40 was also merged into its respective base, but main tree did not include RED tests. New repair branch based on main, #41. No merge performed in this remediation.

RED 45542760055: 11 failed, 417 passed; all four jobs failed as expected. Reapplied exact RED tests plus minimal fix on a69dd3e. GREEN 45543156830 Ubuntu 3.12: 428 passed in 10.45s, default ABSTAIN/stake 0; both Ubuntu jobs succeeded. Windows and latest script commit CI pending at ledger creation.

Actual source run 45543194533, job 138966412725, commit 74095d80: success. Old implementation verified from immutable 2e084eed and Git blob SHA1; both versions run on identical original and derived SHA256-pinned snapshots. Zero added/removed logical match projections; 12620 eligible, 7694 evaluated, exact aggregate and per-fold scores unchanged. Therefore retain existing P1.8c manifest; no new cohort. Save evidence JSON. No official match ID or draw certification.

Ruling: strip outer whitespace only, preserve case, reject blank and self-pairs after stripping, count INVALID_PLAYER_ID instead of crashing. Conservative standard completed-set token validation rejects explicit incomplete markers and abnormal tokens including 0-0. This is not a full match-completion/winner/format verifier (best_of and special-format adjudication not proven); preserve historical extended advantage sets and 13-12. Original older snapshot preliminary inspection had two unusual tokens; this verified impact applies to locked revised cohort only. No raw rows committed.

Next P1.9c: exact pinned local offline input mode (all five seasons; avoid mutable endpoint when local provided); differentiate nominal publisher URL from actual acquisition provenance and raw/derived hashes, expose opt-in normalization CLI. Preserve default historical research-only safeguards. P1.9d environment/manifest, P1.9e full uncertainty, then re-review. No independent reviewer available in current environment; no production claims.
