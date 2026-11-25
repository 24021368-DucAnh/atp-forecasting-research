# P1.8a implementation and P1.8b continuation ledger

Base d4f7f63, stacked draft #36. P1.7c final-head CI 45446839517 passed all four jobs.

- P1.8a initial RED aed0e42 / 45454309592: 8 failed as module missing, 387 passed. GREEN c2a6550 / 45454593269: 395 passed on Ubuntu 3.12; 4/4 CI success. Original/revised Python research run 45454578092 successful, V1 evidence 258e6e0.
- Self-review (no fresh reviewer tool): important finding that a global group counter was presented in season-level row counts but not calculated there; need segmentation of duplicate groups by scope. RED 8e5f0e7 / 45454858551: 2 failed, 395 passed. Fix 96fc134e3; actual V2 research run 45455111670 successful. Full suite run 45455129565 separately checked.
- Ruling: retain V1 evidence as historical receipt, use V2 as current report; never infer per-season group counts from row counts.
- Ruling: source-level duplicate candidate findings are separate from canonical identity adjudication. The exact original three early-season repeated groups differ only in match_num; fourth (Dubai) differs in stats. Source revision removes one main-tour repeated group, while 2021/2022 files are unchanged. Do not modify source or Elo loader in this audit.
- Ruling: 314 connected knockout graphs with one final do not imply true draw completeness; duplicate edges are hidden by graph connectivity. External match evidence is not full source independence or official draw certification. The Stuttgart ATP archive could not be retrieved; independent Sportschau result used instead. No official match number mapping claimed.
- Review boundary: independent reviewer unavailable. Draft retained; no merge.

## Next task P1.8b
Use exact content-pinned source sets, deterministic candidate-key reconciliation, and three separate sensitivity cohorts: locked existing baseline, one logical outcome per strictly identical-except-match_num reviewed main-tour group, conservative exclusion of all rows in unresolved conflicting groups. Do not infer an official canonical match_num or choose conflicting stats. Require exact event/round/identity metadata and source SHA; fail closed on changed candidate group counts or core fields. Record eligible and evaluated counts by year, same-cohort and expanded/reduced descriptive scores, no tuning or selection on holdouts. Preserve historical default; no feature training certification. Test first with synthetic duplicate and conflicting-stat fixtures; run full CI plus both source revisions. Further full-draw verification and player name adjudication remain separate.
