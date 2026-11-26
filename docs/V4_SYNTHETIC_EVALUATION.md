# V4 synthetic prospective commitment and evaluation (S5)

Offline/synthetic only. S4 preview is not a durable forecast. S5 creates
a schema-v4 evidence receipt before the synthetic target result exists.
No independent timestamp authentication, live provider access, training,
export, promotion, scheduling, real performance or wagering claim.

## Upgrade and transaction contract

With an idle trusted writer opened by database.connection.open_writer,
initialize schema versions 1, 2, 3 as documented in V4_SQLITE.md, then
call database.schema_v4.migrate_evaluation(conn). Existing version 3
is checked exactly and upgraded in one explicit transaction; v4 is
verified on retries. Existing v3 tables and records are unchanged.
Three immutable sidecars store commitment payloads, assessment reasons
and outcome labels, and canonical fixed-cohort manifests. Old predictions
without an S5 receipt are not certified or scored. v3 and v4 backup and
restore are supported, with exact schema/integrity checks. Existing
S2 typed inserts, S3 ingestion and S4 preview work on verified v4.
Use trusted factories, UTC clocks, one writer and no raw SQL bypass.
Explicit SQL transaction control in S5 prevents accidental consumption
of caller work and preserves atomic rollback.

## Prospective sequence

1. Register synthetic source/players/fixtures and the fixed S4 model
   version, and supply complete explicit synthetic event metadata.
2. Before any target result is stored, call evaluation.service.register_cohort
   with a synthetic cohort ID, unique fixture IDs (one per match), unique
   registered model IDs, registered_at and cutoff_end. The canonical
   membership and window are immutable; exact replay is permitted.
   Each model has the same fixed target_n. No post-outcome registration
   or retroactive addition. Model versions other than the fixed baseline
   may be registered in the cohort, but S5 cannot fit or infer them.
3. Call prediction.commitment.commit_prediction(conn, fixture_id,
   event_metadata, cutoff=..., created_at=...). V1 requires equal
   normalized clocks, strict pre-scheduled-start, latest available
   fixture and no target result. New commitments also reject any already
   stored target result or superseding/cross-source fixture revision,
   even if those rows claim later clocks. Recompute S4 in the same
   BEGIN IMMEDIATE transaction that inserts the feature, prediction and
   canonical receipt. Stable IDs and SHA256 bind the ordered feature
   vector, selected result IDs, fixture, model, selected event metadata,
   feature and preview digests and created_at. IDs reference immutable
   source records; no dummy label or caller probability. Exact replay
   is a no-op when the recomputed receipt matches; a conflict fails
   closed. get_commitment returns the verified immutable receipt.
4. Ingest synthetic results with S3. evaluate_prediction(conn,
   prediction_id, as_of=...) examines the latest observed result
   revision as of that instant. Missing or unavailable result is
   PENDING, not a stored assessment. A later unavailable correction
   blocks the old score. Ambiguous or wrong source cannot be scored
   and has no trusted assessment row. A known available COMPLETED
   result requires known actual start and publication and strict
   commitment < actual start <= publication <= observation <=
   availability <= as_of. The committed fixture must not be superseded
   by a visible higher revision or other source by actual start; no
   automatic rescheduling transfer. Unknown timing, late, RETIRED and
   UNKNOWN are INELIGIBLE; VOID and WALKOVER are VOID. A terminal
   assessment stores one immutable reason and optional binary outcome
   for the exact result revision. Exact replay preserves the first
   evaluated_at. Conflicting evidence is rejected, not overwritten.
5. evaluation_report(conn, cohort_id, as_of=...) opens its own verified
   read snapshot. For each model, count every member: MISSING, PENDING,
   RECORDED, VOID, INELIGIBLE. Only S5 receipt commitments in the frozen
   inclusive cutoff window count as committed. Only effective recorded
   assessments visible by as_of count as scored. A correction not yet
   evaluated cannot inherit a previous score. Both coverage ratios use
   the fixed target_n. Report grouped summaries by model, tier, surface
   and scheduled UTC month. Matched metrics use the common fixture keys
   with identical outcome/result revision, with explicit unmatched
   counts; no rank over unequal denominators.

Accuracy chooses A at p_A >= 0.5. Log loss clips only the log argument
at 1e-12; Brier uses original probabilities. ECE is the weighted absolute
difference between mean p_A and outcome rate in ten fixed equal-width
bins, last includes 1. Empty eligible samples have n=0 and null metrics.
Synthetic prospective reports must not be mixed with V3 historical
development evidence or later real evidence.

## Limits

Complete synthetic inventories, normalized typed source clocks, local
immutable SQLite records, and the single-writer order are assumed.
Caller clocks/metadata and SHA256 do not prove independent time or
provider authenticity; arbitrary raw SQL/backdated insertions outside
the typed workflow are not certified. Conflicting assessment evidence
fails closed. Only one S4 no-fit baseline inference is supported;
candidate training and independent model lifecycle are S6. UI and
worker deployment are S7. S8 remains LOCKED pending explicit rights
and timing/activation approval.
