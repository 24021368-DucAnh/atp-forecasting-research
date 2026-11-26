# V4 synthetic prediction preview

S4 connects immutable synthetic SQLite revisions to a label-free target,
point-in-time history selection and a deterministic 18-feature snapshot.
It is offline only; V3 source/evidence remain unchanged.

## Eligibility

The caller supplies a complete, versioned synthetic EventMetadata
inventory with explicit UTC event-start dates, observed_at and nullable
available_at. Event dates are not inferred from match dates. The latest
observed metadata revision must be available by cutoff. The SQLite
target must be the latest observed fixture revision for one source,
SCHEDULED, known available, with cutoff strictly before scheduled start.
Any observed target result blocks inference. The historical selector
uses only known eligible completed outcomes, with a 28-calendar-day
event-start embargo relative to both cutoff day and target event date;
same-event and same-match results are excluded. Unknown or unavailable
latest result revisions block stale fallback. No cross-source merging.

## Feature and model preview

Register the fixed no-fit synthetic baseline using the existing S2
writer, an explicit transaction and
prediction.inference.synthetic_model_version(created_at=...).
This produces the SYN-global-elo-v1 model version with fixed algorithm
and configuration digests. The creation clock also serves as a no-fit
training-cutoff convention. It is not evidence of training.

On an idle reader or writer, call
prediction.inference.predict_fixture(conn, fixture_id, event_metadata,
cutoff=...). The service uses a verified read transaction and closes it
on all paths. It returns an immutable InferencePreview containing the
model version, ordered 18-feature values, eligible result IDs, cutoff,
probability and a digest binding the fixture, feature lineage, model
and selected event metadata. The probability is fixed global Elo,
not a fitted ML candidate, and cannot demonstrate future accuracy.

S4.2 tests compare the feature mathematics to frozen V3 on equivalent
synthetic history; stricter availability gates may exclude additional
rows. Real historical parity is pending approved inputs and scope.
No target dummy labels are created by the V4 service. No feature row,
prediction commitment, evaluation or job row is written in S4.3.
S5 owns durable prospective commitment and scoring.

## Operational limits

No real provider or network request, fit, model export or scheduler.
Read-side inventory limits are 100000 entries; caller-supplied metadata
must be complete, trusted and synthetic. Clock/metadata claims are not
authenticated or independent proof of prestart timing. Scheduled start
is not actual start; S5 must verify actual timing before scoring.
SQLite tournament metadata does not yet persist event-start revisions.
Preview digests are local integrity evidence, not externally witnessed
commitments. No dashboard activation in S4.
