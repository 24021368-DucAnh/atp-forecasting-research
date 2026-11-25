# P1.9 — independent review remediation (2026-11-25)

Input: independent review report dated 2026-11-25, 69/100, checkpoint 2e084eed. Review sections 5–9, 13 findings. Source PDF was supplied in conversation, not included in repo. Preserve all prior evidence; do not claim the review is a full independent rerun.

## P1.9a integration incident
Observed current main 932c80ec, all 16 previous PRs closed/merged to their respective targets. Main lost 53 files and has 6 differing files; zero main-only paths versus P1.8c. Ubuntu CI run 45541147214: 22 failed, 313 passed, all four matrix jobs failed. Five previously diverged PRs audited at file/blob level in companion JSON. Earlier PR changes to __main__, paper_ledger, period_risk, documentation, and Elo were superseded by later checkpoint implementations; main contained older variants. Ruling: exact P1.8c tree recovery in new child fb7424a, no main force push/merge. This restores the audited snapshot, not proof of every historical commit's semantic equivalence. Draft #39; require full CI, independent diff review, explicit merge authorization and main CI after merge. Preserve original checkpoint commit and handover. Tag/branch governance remains owner decision.

## Findings / acceptance matrix
| ID | Finding | Track | Acceptance | State |
|---|---|---|---|---|
| P0-1 | Integration | P1.9a | Exact original tree recovery, PR diff evidence, 4/4 CI; independent review and owner-authorized main merge | Candidate created; pending CI/review/merge |
| P0-2 | Missing folds/CI, 50 resamples | P1.9e | 2000 event-stratified resamples, full fold LL/Brier/n, paired surface/global CI, regression schema tests | Open |
| P0-3 | No TML ML/calibration/untouched holdout | P2.1r–P2.5 | Preregister before model experiments; chronology and separate calibration; genuine future untouched split, not presume 2026 untouched | Open |
| P1-1 | whitespace IDs | P1.9b | Reject whitespace-only and same stripped ID; avoid accidental name merge; tests, report impact | Open |
| P1-2 | mutable 2025 endpoint | P1.9c | Explicit offline local dir, all exact raw pins verified before work, no network on offline path, drift rejects | Open |
| P1-3 | nominal vs actual URI | P1.9c | Distinct nominal publisher and actual acquisition provenance, raw/derived hashes, no fake fetch claim | Open |
| P1-4 | dependency lock and eager Pydantic | P1.9d | Platform/version locks generated from actual successful env, CI installs locks; lazy import public compatibility | Open |
| P1-5 | surface worse, batch overshoot hypothesis | P2.1r/P2.4 | Keep baseline unchanged; preregister convex blend, K decay, batch variants, paired CI/reliability; no outcome-driven cherry pick | Open |
| P1-6 | legacy split/rank leakage | P2.1r/P2.2 | Mark legacy scope; new TML event-group splitter/embargo, explicit timestamp availability; rank excluded absent evidence | Open |
| P2-1 | incomplete score filter | P1.9b | Test Default/0-0/incomplete and clear completed score contract; sensitivity vs frozen baseline | Open |
| P2-2 | stale root manifest | P1.9d | Replace stale manifest with deterministic complete tracked-file verification excluding manifest itself; retain historical evidence | Open |
| P2-3 | CLI normalization/scorer | P1.9c/P2.2 | Opt-in CLI flag, research-only skill scorer ATP250 with no required market probabilities | Open |
| P2-4 | cross-calendar year attribution | P1.9e | Report cross-year rows by source season and evaluation fold; distinguish season vs event start year | Open |

Order: integration recovery -> parser regressions -> offline/provenance -> environment/manifest -> uncertainty -> rerun/fresh review -> preregistration -> P2.2. No outcome tuning to 2023–25. Keep all trust flags false, no allocation. Official draw and exact availability remain blocked, source use remains personal noncommercial. Independent review itself did not rerun full pytest/live source. Do not claim 2026 untouched given earlier 2026 research. Any evidence of changed cohort counts must be versioned as a new comparison, not overwrite original results.
