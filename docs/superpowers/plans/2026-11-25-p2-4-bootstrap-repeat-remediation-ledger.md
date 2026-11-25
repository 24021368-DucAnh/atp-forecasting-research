# P2.4 bootstrap repeat comparison remediation (issue #51)

Base: 61ca9bef7573abc85bcfb3a90dcc4e3278fae27c. Branch: research/p2-4-bootstrap-repeat-remediation; draft PR #52.

- RED: ff29f2c89b5544bb54e639017b2e6d7b33d5fe19, CI 45570997433. Manifest passed on all four jobs; Ubuntu 3.11 log: 9 failed, 486 passed, missing comparison function.
- GREEN: f07c16c0a007b10a939ab5916d3507bab48ef644, CI 45571772659. All four jobs passed manifest, full tests and safety smoke checks. Ubuntu 3.11: 251 tracked hashes, 495 passed in 12.18s.
- Offline evidence: docs/research/p2_4_bootstrap_repeat_comparison_evidence_20261125.json. Compared archived aggregate scores on matching support, 8 paired models x 2 metrics x 2 endpoints = 32; global Elo has no self-comparison interval. Maximum absolute endpoint difference 6.439798101894045e-9. No new numerical acceptance threshold.
- Ruling: versioned separate comparison evidence instead of rewriting either original archive or rerunning fits. This satisfies reporting of previously observed endpoints, not proof of independent reproduction. No new source access or holdout access.
- Self-review of implementation diff (no reviewer subagent available): comparison wired into script; archived inputs unchanged; extra P2.4 candidates excluded from P2.3 repeat comparison; numeric and fold/metadata mismatch guards present. No critical defect found in locked-archive scope. Limitations: full historical ML CLI not rerun after change; tests exercise real archived aggregate data, not fresh fitting. Independent review still not performed.
- Deferred minor: existing CI Node.js 20 action deprecation warnings; not changed in this remediation.
- Next gate: full CI after evidence/ledger commit, owner or independent review before integration. P2.5 remains owner-gated. Research-only status, no trusted validation, allocation disabled, stake zero.
