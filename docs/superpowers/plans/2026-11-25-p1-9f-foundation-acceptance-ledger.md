# P1.9f — foundation acceptance and remediation disposition

Original independent review PDF (18 pages, 69/100, checkpoint 2e084eed), findings P0-1 through P2-4 and conditional go/no-go read again at pages 9–18. This is implementer verification, NOT a new independent review or score. Preserve original handover/commit, no source rows committed. Main 874acd5a exactly matches 215/215 files of P1.9e b32c2dab; no open PR at capture, main CI 45560265521 success 4/4 and P1.9e final CI 45554351996 450 tests/214 hashes, pip check, default ABSTAIN/stake 0. Draft #45 directly targets main. No merge by this remediation.

| Finding | Disposition | Evidence / remaining acceptance |
|---|---|---|
| P0-1 integration | PARTIAL | Main exact tree and CI confirmed; all old PRs closed. P1.9a blob matrix preserved. Immutable checkpoint tag and independent semantic diff reviewer pending. |
| P0-2 uncertainty | TECHNICALLY_ADDRESSED | P1.9e full folds, 2000 paired cluster resamples, fixed seed, four intervals; P1.9f exact replay. Descriptive only. |
| P0-3 ML/calibration/untouched holdout | OPEN | P2.1r–P2.5. No ML on new TML cohort, no independent holdout. 2026 cannot be assumed untouched; earlier exposure audit required. |
| P1-1 identity whitespace | TECHNICALLY_ADDRESSED | P1.9b regression 45542760055 -> 45543339152; zero locked cohort change actual run 45543194533. |
| P1-2 mutable endpoint | TECHNICALLY_ADDRESSED | P1.9c local five raw exact pins, no network fallback, actual offline run 45545825591; P1.9f repeat. |
| P1-3 provenance | TECHNICALLY_ADDRESSED | Separate actual request URI, nominal publisher, acquisition mode, raw/derived SHA; local null. Final redirect/timing not attested. |
| P1-4 dependency coupling | TECHNICALLY_ADDRESSED | Four observed version locks, no eager Pydantic imports, pip check and CI. No wheel/build/OS hash lock. |
| P1-5 Elo hypotheses | OPEN | Fixed baselines preserved; preregister variants and compare matched cohort with calibration/paired CI in P2.4, no retrospective tuning. |
| P1-6 legacy temporal leakage | OPEN | New TML-specific splitter and pre-event feature contracts in P2.2; legacy Tennis-Data research not validated for TML; no current ranks absent availability evidence. |
| P2-1 score filter | TECHNICALLY_ADDRESSED | Default/unfinished/0-0/whitespace tests and zero cohort drift; syntax only, not official completion certification. |
| P2-2 stale manifest | TECHNICALLY_ADDRESSED | Canonical tracked Git SHA256, excludes itself; CI gate. |
| P2-3 CLI/skill scorer | PARTIAL | Normalization CLI pin guard done; standalone skill-only scorer incl ATP250 and no market probabilities remains P2.2. |
| P2-4 calendar attribution | TECHNICALLY_ADDRESSED | 54 eligible cross-calendar rows from 2025 source in 2024 fold; raw 83 distinct. |

Counts 8 technically addressed, 2 partial, 3 open. No independent rescoring.
RED 45560466554: missing module collection error. GREEN actual run 45560592222 job 139023077923, commit 4ee56efe: 11 tests passed 0.04s and actual online/offline replay success. Exact equality of manifest, SHA, eligible, evaluation fold counts, aggregate, full folds, paired bootstrap and calendar attribution, evaluation status against archived P1.9e. Five raw/derived pins and acquisition modes verified. Offline guard uses Python socket/acquisition function patches, not OS sandbox; local bytes unchanged. 12620 eligible, 7694 evaluated, 2000 bootstrap, no unsafe flags. Archive output JSON. Final manifest regeneration and full matrix CI on final head still required before accepting PR.

## Gate decision
- Offline exploratory research: CONDITIONAL GO to P2.1r protocol design, then P2.2 only after protocol registered and integration/final CI verified. This is not independent review acceptance.
- Independent evaluation / benchmark publication: NO-GO, lack genuine untouched split, calibration, official draw verification and external independent rerun.
- Production/commercial: HARD NO-GO, outside current scope. Source noncommercial rights, no verified match timestamps or publication availability, no live predictions/allocation. Preserve all trust flags false.
- Original reviewer recommended 2026 untouched; cannot adopt without exposure audit. Reviewer also proposed official ATP ranking baseline; current-match rank cannot be assumed available pre-event. Research design must explicitly handle evidence and eligibility. A future genuinely unseen period must be independently reserved before data access. No model fitting/tuning in P1.9f.
- Tag creation not supported by current connected repository tool; exact immutable commit SHA remains recorded; owner may create protected tag separately. No claim tag exists.
