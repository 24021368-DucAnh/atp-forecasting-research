# V4 synthetic ingestion - offline contract

S3 extends the accepted S2 SQLite v3 database. It does not activate
real providers, internet requests, credentials, fitting, prediction,
scoring, a scheduler or dashboard database integration.

## Pipeline

1. Verify idle writer, exact v3 schema, foreign keys and recursive
   triggers, synthetic job ID, clock order and unused terminal job ID.
2. Verify explicit SourcePolicy opt-in, registered SYNTHETIC/LOCKED
   source, exact reserved endpoint and bounded adapter configuration.
   A denied request never calls the transport or sleep callback.
3. Fetch using a caller-supplied trusted in-memory fake transport.
   At most 3 attempts, transient failures only; delays 0.25/0.5 s.
   Returned bytes must be nonempty and at most 1 MiB. SHA-256 binds
   exact returned bytes. No HTTP implementation is shipped.
4. Within BEGIN IMMEDIATE, reverify schema and source, normalize
   JSON via explicit provider crosswalks, insert snapshot and revisions,
   then commit a SUCCEEDED terminal job together with the whole batch.
5. On recognized data failure, roll back the data transaction before
   persisting a separate FAILED job and sanitized quality issue.
   Operational SQLite or unexpected failures propagate without a
   fabricated terminal receipt. BLOCKED requests get job receipts
   but no quality issue (the source might not exist).

## Synthetic input contract

Use only a registered synthetic source and pre-created source-scoped
player/match aliases. The parser never creates identity mappings.
A changed participant pair is rejected, not automatically remapped.
The fixed opaque fake keys are:
- https://synthetic.invalid/v1/fixtures
- https://synthetic.invalid/v1/results

Each UTF-8 JSON document has one matching root key, fixtures or results,
with at most 1000 rows. No duplicate object keys or unknown fields.
Fixture fields: match_id, player_1, player_2, revision, scheduled_start,
state. Result fields: match_id, player_1, player_2, revision, published_at,
actual_start, state, winner. All fields must be present, nullable only
where S2 permits. Positive integer revision, exact provider IDs,
canonical sorted participant pair. Known timestamps normalize to UTC.
Unknown time remains null. The caller supplies observed_at and
available_at separately from JSON; these clocks are synthetic claims,
not independently verified time evidence.

## Invocation example

After initializing the v3 DB and registering synthetic identity data:

```python
from atp_lab.ingestion.adapter import SourcePolicy, FIXTURES_ENDPOINT
from atp_lab.ingestion.pipeline import ingest_batch

class FakeTransport:
    def fetch(self, url):
        return b'{"fixtures":[]}'

report = ingest_batch(
    writer, SourcePolicy("SYN-feed", enabled=True),
    FIXTURES_ENDPOINT, FakeTransport(),
    job_id="SYN-ingest-001",
    started_at="2026-01-02T13:00:00Z",
    observed_at="2026-01-02T13:01:00Z",
    available_at=None,
    ended_at="2026-01-02T13:02:00Z",
    sleep=lambda seconds: None,
)
```

The example uses an empty batch and deliberately fake clocks.
Writer must already be verified and idle. A completed job ID cannot
run again; use a fresh unique synthetic ID for another invocation.
The job attempt field is 1 for each invocation; it does not count
the internal adapter retry attempts. No transaction remains open
during transport or backoff. Use one trusted writer/orchestrator.

## Revision and recovery semantics

A snapshot ID binds source, endpoint, byte digest and normalized
observation time. Revision IDs bind source, canonical match, revision
and record kind. Exact repeated records are no-ops. A later observation
of the same canonical provider fields may add a snapshot but keeps
the original revision, observation time and availability unchanged.
Earlier observations, conflicting metadata at the same observation,
different stable IDs or changed provider fields at the same revision
reject the entire batch. A corrected result requires a new revision.
A later re-observation snapshot has no extra row-level replay link
in the S2 schema; this is not an exhaustive observation history.

The failure ledger stores fixed reason codes, not exception messages,
credentials or raw payloads. If writing the failure ledger also fails,
the error propagates. A crash before terminal commit may leave no
job receipt, and a new invocation may need to fetch again. No durable
lease, exactly-once external fetch, automatic recovery or scheduler.
The injected transport is trusted caller code, not sandboxed; the
payload cap is an in-memory bound, not a network streaming limit.

Real data authorization and actual provider limits belong to S8.
No synthetic ingestion evidence proves real source rights, temporal
availability, predictive accuracy or production readiness.
