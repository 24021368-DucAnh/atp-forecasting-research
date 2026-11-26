# S4.3 - Read-only SQLite assembly and deterministic synthetic inference

Base S4.2 GREEN fc5aa3563336666a2fa1fcf4c48fb7813c84d3b1; issue #67, PR #68.
Raw core run 45860846336: 920 passed/1 intentional UI skip each of four
jobs; UI 45860846390 both 9 passed; 307 hashes and pip check all six.

No real source, training, model artifacts, database schema migration,
prediction commit or scoring. S5 owns durable forecast commitment.
New prediction/inference.py and test_prediction_inference.py.
Read-only service predict_fixture(conn, fixture_id, event_metadata,
*, cutoff) -> immutable InferencePreview(match_id,fixture_id,model,
features,probability_a,digest). Open own read transaction on idle
connection; verify exact schema in snapshot; close own transaction on
all paths; never write. Caller transaction must remain untouched.
Invalid eligibility raises InferenceError(ValueError), schema/SQLite
operational failures propagate. Only synthetic registered source
mode SYNTHETIC and rights LOCKED. Use bound SQL, exact types, canonical
UTC and source IDs. Fetch only as-of rows (observed <= cutoff), verify
clock and identity contracts via temporal. Reject missing requested
fixture, latest observed revision mismatch, multiple visible sources,
unavailable/cancelled/postponed/unknown target, known target result
observation (any state), cutoff >= scheduled start, and invalid pair.
Later observations are not used. Future valid correction cannot
change preview. Canonical match joined from S2 matches and tournaments;
fixture participant pair must agree with canonical pair. No automatic
cross-source reconciliation. Target match results blocked before
inference, others go through S4.1 eligibility. Read historical
revisions with registered source and matching canonical identity;
require explicit metadata for visible result events, fail closed
rather than infer dates. No training or live data.

EventMetadata(tournament_id,revision,event_start:date,observed_at,
available_at) frozen; exact SYN IDs, positive exact int, known UTC
observation, optional availability >= observation, exact date.
Explicit caller-provided synthetic metadata inventory; not independently
authenticated. Select highest observed revision as of cutoff, reject
duplicate visible keys and unknown or unavailable latest metadata for
required events. Do not use future metadata. Bind selected metadata
for target and eligible result events to preview digest, even same
date revision changes. No schema changes; caller responsible for
providing complete revision inventory. Strict event-start dates UTC.
Bound result rows and metadata to 100000 entries; fail closed on limit.
Clock metadata and known scheduled time are not proof of actual start.
S5 must verify actual timing before scoring. No persisted feature
payload or commitment in S4.

Fixed no-fit synthetic baseline: model ID SYN-global-elo-v1, model
digest SHA256 of fixed algorithm specification, config digest binds
FEATURE_VERSION and algorithm parameters; synthetic_model_version(
*,created_at) -> database.forecast.ModelVersion with training_cutoff
equal to created_at as no-fit convention, normalized UTC, scope
SYNTHETIC. Caller registers via existing S2 typed API; read exact
registered record, verify both digests and no-fit convention, created
<= cutoff. Probability uses frozen global Elo difference with same
V3 clip and formula, no coefficients fitted or model selection claim.
Preview digest canonical SHA256 of version, model full fields,
match/fixture IDs, feature digest/cutoff, selected metadata full
fields, probability. No claim of authenticated or persisted
commitment. Synthetic parity of features verified in S4.2.
RED first, expected missing inference module. GREEN implement, docs
and full regression. Audit entire S4, separate review decision.
