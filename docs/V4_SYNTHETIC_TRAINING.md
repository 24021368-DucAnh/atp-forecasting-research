# V4 S6 — Controlled synthetic training and lifecycle

S6 implements offline synthetic candidates only. It does not authorize
real data collection, actual historical refitting, real model export,
production promotion, scheduling or a real-world performance claim.
All clocks, source metadata and owner approval receipts are local
synthetic inputs, not independent authentication.

## Install and migrate

Use the pinned core ML/test environment on Windows or Ubuntu. The
Streamlit environment remains separate. S6 does not train at import
time, from UI rendering, or by a background job. The trusted local
single writer migrates v1 through v4 as documented, then calls
database.schema_v5.migrate_training(conn). This verifies exact v4 before
an atomic additive v5 migration and verifies exact v5 on replay.
Schema v5 adds three immutable sidecars: training_protocols,
candidate_artifacts, model_lifecycle_events. Old records are untouched.

## Register, select, fit, freeze

1. Use training.protocol.TrainingProtocol and register_protocol to
   register synthetic protocol/cohort IDs, UTC registration and
   training cutoff, half-open event-date fit/calibration windows, future
   evaluation start/end clocks, and explicit fit/cal/matched minimum
   sample counts (each >=2). Windows cannot overlap. The future cohort
   must not already exist. Registration is immutable; an equivalent
   normalized replay is a no-op.
2. training.dataset.collect_dataset uses only the fixed baseline's
   verified S5 prediction and effective stored assessment receipts.
   It selects all eligible canonical examples from the declared
   windows, checks one match and consistent event identity per split,
   exact original feature order/digest/lineage, and no current-match
   label among the stored feature history. Fit labels and 28-day event
   maturity must precede calibration start; calibration labels and
   maturity must be known by the training cutoff. Effective revisions
   are selected as of the cutoff, unavailable newer revisions block
   stale fallback. No retrospective feature reconstruction. Reasons
   for exclusion and all selected IDs, labels, clocks and feature values
   are hashed in the immutable dataset. Both unmirrored splits require
   both classes and their preregistered minima; no fallback or expanded
   dates when support is insufficient. The current local inventory and
   accepted synthetic clock claims are the evidence boundary.
3. Explicitly call training.registry.train_candidate(conn, protocol_id,
   created_at=..., model_dir=...). Freeze clock strictly after training
   cutoff and no later than evaluation start. Fit uses fixed
   LogisticRegression(C=1, solver=lbfgs, max_iter=2000, random_state=29)
   on original and mirrored fit examples. StandardScaler is fitted only
   on mirrored+original fit data. Negate the first 10 signed features,
   retain the last 8; symmetric probability averages p(x) and 1-p(swap).
   Fit a second fixed logistic Platt calibrator only on the disjoint
   calibration symmetric-probability logits and mirrored labels; mirror
   the calibrated output again, clip to [1e-12,1-1e-12]. No selection
   on future evaluation outcomes, no random cross-validation, no model
   family/hyperparameter search. Single-threaded fit, reproducibility
   within a runtime/tolerance, not bitwise equivalence across OS/libs.
4. The artifact is bounded canonical UTF-8 JSON (<=8 MiB), with
   finite exact 18-feature scaler/coefficients, calibration and frozen
   protocol/dataset/config/dependency/code hashes. No pickle/joblib.
   Supply an existing absolute trusted local directory named
   model_artifacts (ignored by Git), under the private repo or another
   private location; no traversal, symlink/reparse point or unexpected
   file type. Hash-derived name, exclusive staging and verified
   same-directory no-clobber hard-link publication, no replace fallback.
   Training runs outside the writer transaction; selection is rechecked
   under a single writer transaction before publication. The model
   version and exact artifact bytes in the registry commit together.
   If publication succeeds but SQLite insertion fails, an unregistered
   hash-named orphan may remain; exact-byte retry may reuse it. No
   automatic orphan removal or overwrite. This assumes a trusted
   single-user directory and local filesystem supporting hard links,
   not concurrent hostile directory replacement or power-loss proof.
   Exact registered protocol replay loads and verifies bytes, never
   fits again. A missing or damaged artifact denies new inference.

## Prospective evaluation and manual selection

Use prediction.commitment.commit_prediction with explicit candidate
model_id and model_dir; the S4 baseline remains the default. Candidate
artifact and model digest are verified in the same snapshot as S4
features and S5 commitment; model frozen before the cutoff, target
event after training cutoff, consumed matches/events denied. The
candidate has a separate inference preview version; old S4/S5
probabilities and digests remain unchanged. Historical candidate
commitments can be verified using the frozen DB receipt if a local
artifact is lost; that does not permit new inference.

Register the exact preregistered subsequent S5 cohort after freeze
with baseline and candidate IDs, within the declared evaluation
window, before its target results exist. Use the same fixture, cutoff
and feature digest for fair comparisons. Evaluate each model with
S5's revision-aware policy. candidate_comparison returns fixed cohort
counts, coverage, grouped metrics and matched metrics only on the
same fixture, outcome/revision and information set. Missing,
unscored, or different information sets are counted, not silently
compared. The comparison digest also binds exact result revision,
prediction, commitment, feature and assessment identities for each
scored row plus per-fixture exclusion reasons, so even a same-winner
correction changes the approval evidence. Log loss delta (candidate minus baseline) is primary;
accuracy, Brier and ECE remain descriptive. The window must close
and the preregistered matched minimum be reached for
SUFFICIENT_SYNTHETIC. This is support for a manual review, not
statistical power, superiority, real skill, or promotion authority.

Initial active_model_id is the fixed baseline. The synthetic
simulation API promote_candidate requires explicit OwnerApproval:
synthetic approval ID, PROMOTE, exact current and destination model
IDs, destination model/config digests, current comparison digest,
normalized decision clock equal to comparison as_of, approved=True.
It revalidates matched evidence in the transaction, rejects earlier
approval clocks if later cohort evidence already exists, and writes
an immutable selection event with predecessor digest. No automatic
champion or implicit model replacement. rollback_promotion requires
an explicit ROLLBACK approval naming current model, predecessor model
of the last promotion, predecessor digests, last promotion event
digest and a later decision clock. Both exact replays are no-ops.
Read-only active_model_id verifies the append-only selection chain.
Use it explicitly for future synthetic commitments; existing APIs
still default to baseline. Old commitments and assessments never
change. No actual production promotion or security authorization
is provided by these synthetic receipts.

training_readiness counts currently eligible distinct mature baseline
matches not previously recorded as eligible and already mature at the
last checkpoint. This conservative history rule excludes reactivated
matches even if an intervening revision was unavailable, and never
counts them as NEW. Weekly (>=7 days)
and 200 new outcomes are operational request flags only, not power
or automatic training. No scheduler is enabled.

## Backup and recovery

Use S2 verified DB backup/restore (recognizes exact v5); separately
retain the private model_artifacts files and verify their content
against the immutable DB receipt. Backup DB does not copy external
artifacts. Never replace a live DB or model file; exact-byte orphan
reuse is allowed, cleanup is manual after checking registry references.
No raw data/artifact output is tracked. V3 historical development,
synthetic prospective and future real evidence remain separate.
S7 adds the local worker/UI; S8 source/rights/activation remains LOCKED.
