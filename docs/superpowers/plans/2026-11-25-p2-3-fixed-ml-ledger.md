# P2.3 fixed ML and calibration ledger

Base main 83226ace; exact 235-file tree matches P2.2 repair 2a384cae, both final PR CI 45567495475 and main CI 45568225110 4/4 pass. PR #49 direct to main. Owner TIEP after scoped proposal interpreted as approval of private noncommercial exploratory research only. Public TML README reviewed 2026-11-25, allows personal educational noncommercial research, prohibits commercial model training without written permission and raw redistribution; third-party rights not independently verified. No use of legacy source or model publication. Exact permission SHA256 2783d980d1ee2488c35a9206a2b270a71e78941c1a758a161aebf0a3c6b223d6; protocol 93776dc9949c6c49c16e8172630b606cd61fe328b25ce08a796a06b8ced3bca6; manifest b9b55b6c75f1f43394b3e69d19c6b791faedc8539908608ecf1d74dfaabcb8fb. Explicit CLI opt-in and pinned file contract, not security/authentication or blanket rightsholder permission. Existing eligibility=0 and all trust flags false.

RED 45568397519: missing tml_research_ml module collection error. GREEN actual run 45568559438, job 139049296198, commit 6a9deee6: six targeted tests passed in 2.08s, actual source replay success. All nine candidates scored on 7694 exact development evaluation keys in 2023/24/25. No model or per-match forecast export. Logistic and XGB fixed parameters, mirrored fit/calibration, fit-only scaling, frozen models during evaluation; both calibrators separately fit on calibration. Calibration slope/intercept descriptive, undefined for degenerate/separated/nonconvergent. Full scores, fold diagnostics, reliability and paired uncertainty saved in JSON.

| Candidate | Log loss | Brier | ECE |
|---|---:|---:|---:|
| coinflip | 0.6931471805599453 | 0.25 | 0.009357941252924329 |
| global_elo | 0.6300670180626627 | 0.22063010972181715 | 0.017689984319008752 |
| logistic_isotonic | 0.6780027732534298 | 0.2180586216842264 | 0.017625097785164724 |
| logistic_platt | 0.6213113230318553 | 0.21651241497585688 | 0.016400929343092466 |
| logistic_raw | 0.6257999476381354 | 0.21809589994650813 | 0.035848549458810296 |
| surface_elo | 0.6320572443209462 | 0.22114242367968637 | 0.03390648139384289 |
| xgboost_isotonic | 0.6279148639812077 | 0.21764931643629792 | 0.01881489975246885 |
| xgboost_platt | 0.6228630631041587 | 0.21699748976243505 | 0.012840950279232103 |
| xgboost_raw | 0.6256230409463953 | 0.21805349774154076 | 0.02982951821030648 |
 
Logistic Platt and XGB Platt LL intervals versus global below zero, descriptive conditional on previously examined 2023–25, not independent validation. Logistic isotonic worsens LL and is retained; no posthoc tuning or champion designation. Rank and future holdout remain blocked. P2.4 fixed preregistered feature ablations and Elo variants are next, no model selection or new data. Final full CI and canonical manifest required; no merge by implementer. 
