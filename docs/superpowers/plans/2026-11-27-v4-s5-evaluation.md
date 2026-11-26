# S5 — Synthetic prospective commitment and evaluation

Refs #69. Exact accepted S4 base eaa6ac264eb6d5d99a9d88c2c282ffc99a2f3f17.
Postmerge core 45865459556: all four 940 pass/1 intentional UI skip, 311
manifest hashes, clean pip check. UI PR-only: exact-tree 45862262525,
both 9 passed. Binding V4 design and handoff Task 1A-D; this is the
implementation contract, not a new product scope. One stage PR.

## Decisions and interfaces
- Additive schema v4 (no rewrites of v3 tables or V3 research): immutable
  prediction_receipts, assessment_receipts and evaluation_cohorts.
  Verify exact schema v3 before migration, exact v4 after, FK and marker;
  transaction rollback, v3/v4 backup/restore and existing typed APIs.
  Existing v3 rows have no S5 certification merely by migration.
- Reuse S4 math in one BEGIN IMMEDIATE writer transaction: internal
  snapshot-bound computation, unchanged public read-only preview API.
  commit_prediction(conn, fixture_id, event_metadata, *, cutoff,
  created_at, model_id=MODEL_ID) -> immutable Commitment with prediction,
  feature and canonical receipt_json. Normalize and require cutoff equal
  created_at. Only S4 registered no-fit baseline. Reject new commitment
  if any target result already exists or any other source/newer fixture
  revision already exists, even when timestamp claims are later.
  Existing exact replay can return immutable receipt after later results;
  different content is conflict. Receipt binds version, normalized clock,
  fixture/model, selected event metadata, ordered feature values, selected
  immutable result IDs, preview/feature digests; SHA256 of canonical JSON
  stored as commitment_digest. No caller-supplied probability or digest.
  Atomically insert feature, prediction, receipt or roll back all.
- evaluate_prediction(conn, prediction_id, *, as_of) -> Assessment with
  status/reason/result_id/outcome_a/evaluation_id/evaluated_at. No scoring
  without S5 receipt. Choose highest observed revision as of normalized
  time; source must match committed fixture, no cross-source arbitration.
  No result or latest unknown/future availability PENDING (no evaluation
  row); do not revive earlier assessment. Known available COMPLETED only
  with actual_start and published_at, valid winner, ordered clocks and
  strict created_at before actual start and result visibility. Any other
  fixture revision observed by actual start superseding committed fixture
  invalidates scoring; no automatic reschedule transfer. VOID/WALKOVER
  explicit VOID, RETIRED/UNKNOWN/unverified/late INELIGIBLE. Immutable
  assessment reason and outcome linked to evaluation/result; one terminal
  assessment per prediction/result, exact replay returns original first
  evaluated_at; new result revision appends. Evidence conflict fails
  closed, no replacement. Unknown availability does not create terminal
  receipt. No claim of authenticated synthetic clocks.
- register_cohort(conn, cohort_id, fixture_ids, model_ids, *,
  registered_at, cutoff_end) -> frozen Cohort. Register unique fixture
  IDs (unique matches), model IDs, explicit window before any target
  result persisted; all fixtures known eligible prestart, models registered
  by registration. Exact replay allowed, conflicting content rejected.
  One immutable canonical membership manifest with digest; references
  validated against append-only source tables. No post-registration
  changes. Report as_of >= registered_at, model/fixture pair denominator
  fixed; only S5 commitments in window, evaluation receipts visible by
  as_of and matching effective result/eligibility. Explicit MISSING,
  PENDING, VOID, INELIGIBLE, RECORDED counts/reasons. Prediction and
  scored coverage distinct; no silent drops. Model, scheduled month,
  tier and surface grouping. No rank or mixed scope aggregation.
- metrics.score_metrics(rows) where rows=(p_A,y_A) validates finite
  probabilities and exact binary labels; accuracy p>=.5 chooses A,
  raw Brier, LL clipped 1e-12, ECE 10 equal-width bins (last includes 1),
  empty null metrics. matched_metrics maps model->fixture->(p,y,result_id)
  and compares only common keys with identical outcome/revision, explicit
  matched_n; no ranking. Report synthetic prospective only. Other model
  versions may be registered in cohorts but no fit or new inference
  algorithm until S6; unmatched/missing coverage is explicit.
- Use legacy factory connections or explicit SQL transaction control;
  reject caller-owned transaction without consuming it. Synthetic
  timestamps and complete inputs are caller claims; malicious/backdated
  raw SQL and independent time attestation outside scope. New commits
  cannot be manufactured after target outcomes are already persisted.

## Test-first batches
RED one stage-wide test file (migration, atomic writes/replay, no
retrospective/stale commit, evaluation policy, corrections and fixed
coverage, matched metrics, actual S3 fake ingestion on v4, restart and
backup/restore, immutable sidecars). Verify intended missing S5 API
failures and unchanged prior suite. GREEN implement all slices, docs
and manifest, verify four core and two UI raw logs on exact HEAD.
No local full-suite claim if DNS/checkout unavailable. No real fetch,
fit, exports, promotion, scheduler, or S6. Owner review/waiver and
exact-head approval required before merge.
