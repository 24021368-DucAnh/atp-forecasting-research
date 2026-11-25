# P2.2a–d implementation and evidence ledger

Protocol P2.1r V1 merged at b62ca307, 225/225 tracked blobs match protocol candidate ab72a3af. Protocol file SHA256 93776dc9949c6c49c16e8172630b606cd61fe328b25ce08a796a06b8ced3bca6. No protocol change. Cohort manifest SHA256 b9b55b6c75f1f43394b3e69d19c6b791faedc8539908608ecf1d74dfaabcb8fb.

RED 45566762577 collection missing module. GREEN actual research 45566960798 / job 139043992839 / 810ace91: 16 passed in 0.09s, successful locked replay. All 12620 eligible rows have unique stable keys and 18 feature values. Shuffled input determinism and feature orientation roundtrip pass. Exact same 7694 historical evaluation keys, fold counts 2600/2647/2447; 250 evaluation rows have at least one player with no prior matured history, retained. Original Elo LL matched within 1e-12. Evaluation tiers 250=2837, 500=1317, G=1463, M=2077. Fit/calibration/evaluation partitions meet registered row/event support; fit and calibration both outcome labels. No fitting performed.

| Year | Fit | Calibration | Gap | Evaluation | Warmup | Future |
|---|---:|---:|---:|---:|---:|---:|
| 2023 | 1284 | 964 | 284 | 2600 | 2394 | 5094 |
| 2024 | 3854 | 1109 | 169 | 2647 | 2394 | 2447 |
| 2025 | 6490 | 1071 | 218 | 2447 | 2394 | 0 |

Baseline comparison remains descriptive: Global LL 0.6300670180626627, Brier 0.22063010972181715, ECE 0.017689984319008752; Surface LL 0.6320572443209462, Brier 0.22114242367968637, ECE 0.03390648139384289; Coinflip LL 0.6931471805599453, Brier 0.25, ECE 0.009357941252924329. All 100% coverage on the actual locked reference key set; ECE is binned descriptive, not a standalone ranking criterion. Brier decomposition binned with residual; calibration slope/intercept deferred to P2.3. No ranking source and no official draw/timing attestation. Skill scorer accepts an explicit reference set; 100% coverage means coverage of supplied reference, so P2.3 must derive full expected evaluation reference from locked split, verify exact keys/counts, not choose a subset. Historical 2023–25 already inspected, no independent claim.

Integration incident: #47 merged externally before manifest refresh. Main be219d8b exactly matches all 232 tracked blobs of 810ace91; no missing or modified paths. CI 45566967068 failed all four at canonical manifest gate, not at tests; main run 45567286699 also requires verification. No revert or direct push. Repair branch from main includes actual evidence, ledger, manifest-only workflow and refreshed manifest. Final complete suite and manifest check required before merge; no owner approval requested for technical repair. Do not merge before CI complete.

## Owner decision required before P2.3
Existing production eligibility is zero. Propose narrowly scoped, explicit exploratory fitting permission only on locked 2021–2025 TML bytes, with exact protocol and manifest hashes above, fixed models and separate fit/calibration partitions, retrospective outcomes only. No live/production certification, no odds, no allocation, no raw or trained-model redistribution, no future holdout access, no use of rights-unverified legacy source. Keep existing policy and all trust flags unchanged. This proposal is not permission granted; owner approval and source-use confirmation required. Once approved implement separate explicit research capability, tests for scope and deny-by-default, fixed ML/calibration and ablation. Future independent custody separately required. No independent reviewer available.
