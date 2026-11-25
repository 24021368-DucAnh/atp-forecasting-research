# P2.4 fixed ablation and cross-platform pin repair

Base main 611b1633, exact 243 tracked blobs of P2.3 41142ff9. PR #49 externally merged despite two Windows failures (482 passed, 1 failed on each, Ubuntu 483 passed); main run 45569164894 also failed. RED 45569348022 demonstrated missing ablation module and Windows checkout hash mismatch. Windows working-tree hashes F6B83FE0AAE5A1CA3A19C57E0CA0E9C7E19B75EE40EDB104CFA510CD8F6D3DFB and FBAEC4D1B89847EBEFD9E8757EC55389794799DEEE322C48F3A8FB6A1969D418; eol unspecified. GREEN 45569464895 Windows pin job 139052245819 verified exact original hashes and eol lf for both after .gitattributes. No changes to protocol bytes, permission bytes, verifier or expected SHA. No direct main edit. Full matrix CI still required.

Actual run 45569464895 job 139052245452 commit ad373a95, 9 targeted tests passed 1.81s, historical research succeeded on all 7694 evaluation matches, exact locked inputs. Feature blocks fixed before ablation execution: first 3, first 15 incl support, all 18. Fixed parameters, same fit/calibration/evaluation partitions, mirrored orientation, raw/Platt/isotonic all retained. Three Elo variants separate, no combined changes. No new sources or future holdout access.

| Candidate | LL | Brier | ECE |
|---|---:|---:|---:|
| coinflip | 0.6931471805599453 | 0.25 | 0.009357941252924329 |
| convex_surface | 0.6281759014447633 | 0.21984647815410335 | 0.012462495893777173 |
| decay_k | 0.6456874753279701 | 0.22592952593115495 | 0.06129238631260584 |
| global_elo | 0.6300670180626627 | 0.22063010972181715 | 0.017689984319008752 |
| logistic_elo_history_isotonic | 0.6780027650554562 | 0.2180586179917404 | 0.017625102351601626 |
| logistic_elo_history_platt | 0.6213113232022122 | 0.21651241501159724 | 0.016400930147701605 |
| logistic_elo_history_raw | 0.6257999485306605 | 0.21809590026499154 | 0.03597852910494805 |
| logistic_elo_only_isotonic | 0.6798191187066274 | 0.2204756308412389 | 0.017024075858613708 |
| logistic_elo_only_platt | 0.627451919473467 | 0.21949730937094697 | 0.011331297512154913 |
| logistic_elo_only_raw | 0.6299316964392567 | 0.22038181226101008 | 0.02515306472200242 |
| logistic_isotonic | 0.67800276517908 | 0.21805861804933727 | 0.01762510223762703 |
| logistic_platt | 0.6213113231986881 | 0.21651241501108331 | 0.016400930131165406 |
| logistic_raw | 0.6257999485295728 | 0.2180959002645909 | 0.035978528991800686 |
| mean_batch | 0.6903116778815791 | 0.2481549908819523 | 0.061150017816757676 |
| surface_elo | 0.6320572443209462 | 0.22114242367968637 | 0.03390648139384289 |
| xgboost_isotonic | 0.6279148639812077 | 0.21764931643629792 | 0.01881489975246885 |
| xgboost_platt | 0.6228630631041587 | 0.21699748976243505 | 0.012840950279232103 |
| xgboost_raw | 0.6256230409463953 | 0.21805349774154076 | 0.02982951821030648 |

Descriptive findings: Logistic Platt Elo+history and all 18 effectively identical in this experiment; Elo only Platt improves over global, history block further improves observed LL. No direct paired CI for incremental feature-block contrast in V1; cannot claim statistically established incremental effect from separate intervals vs global. Convex surface LL interval vs global entirely below zero; decay K and mean batch intervals above zero. All results reported; no champion selection. Isotonic logistic poor LL retained; no posthoc rounding/tuning. Repeated P2.3 aggregate/per-fold proper score max absolute difference 2.343463301190951e-8, consistent with prior repeat; logistic raw ECE difference 0.00012997953299039022. XGB and frozen baseline proper scores identical. Not bitwise repeatable and not independent verification.

P1-5 ablation and P1-6 temporal research pipeline technically addressed within retrospective protocol; P2-3 skill scoring implemented. P0-3 still open for independent untouched evaluation; no claim independent review, new score or official ATP draw/availability certification. All eligibility/trust flags unchanged. No financial metrics or per-match forecast exports. P2.5 requires owner-approved independently held future interval, source-use confirmation and custodian; do not access new outcomes or select champion from development scores. Final CI and integration verification, then owner decision on independent evaluation design.
