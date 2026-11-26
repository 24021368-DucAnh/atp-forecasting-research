# V4 SQLite persistence - offline synthetic research

Scope: S2 database foundation, identity, forecast provenance and recovery,
with S5 additive synthetic commitment and assessment receipts.
This is a local persistence layer, not a production tennis-data service.
Offline synthetic prospective scoring is described in
[V4_SYNTHETIC_EVALUATION.md](V4_SYNTHETIC_EVALUATION.md).
Real ingestion, actual model fitting, model artifact export, scheduler
and UI database wiring remain locked or deferred.
V3 historical engine and evidence are unchanged.

## Local files and connections

Keep all database files, backups, WAL/SHM sidecars and temporary files
under the ignored data/atp_lab/ directory (or a private local directory
outside Git). Do not commit database files or put secrets in job/quality
receipts. Use local NTFS on Windows or a local Linux filesystem supporting
hard links and SQLite locking; do not assume network/FAT support.
A single trusted worker owns writes. open_writer(path) enables WAL,
foreign keys, recursive triggers and a five-second busy timeout.
open_reader(path) opens an existing file with SQLite mode=ro and query_only.
Callers close connections explicitly. Read-only access to a live WAL DB
requires access to its WAL/SHM files or permission for SQLite to manage
them in the local directory. SQLite may create source WAL/SHM sidecars
when opening a read-only connection, even if verification later rejects
that database. These are not published backup or staging files. Never
remove source sidecars as part of backup cleanup. Do not use immutable=1
on a changing DB.

## Explicit migrations

Use a new synthetic database, initialize v1 with migrate(), upgrade v1
to v2 with migrate_identity(), upgrade v2 to v3 with
migrate_forecast(), then upgrade v3 to v4 with migrate_evaluation().
For an existing database invoke the migration for its known version;
migrate_evaluation() upgrades verified v3 or verifies exact v4 on retry.
Never reset user_version or rerun earlier migration entry points against
a later version. Unsupported or damaged schema fails closed.
Migration operations own their transactions and require an idle writer.

v1: bootstrap marker. v2: nine identity/fixture/result tables plus marker.
v3: six forecast/operational tables, total sixteen including marker.
v4: three immutable commitment, assessment and cohort receipt tables,
total nineteen. Existing v3 rows remain unchanged; legacy predictions
without an S5 commitment receipt are not certified or scored.
Use explicit caller BEGIN IMMEDIATE / commit / rollback around record
writes. Same canonical record retry is a no-op; conflicting replay fails.
The schema preserves immutable source, identity, result and forecast
records. Explicit provider aliases are required to resolve identity.
Unknown timestamps remain NULL where allowed. Typed services normalize
known timestamps to UTC. Raw administrator SQL is outside the trusted
service contract and the ledger is not tamper-evident against administrators.

## Backup and recovery

The following example creates a new synthetic database and snapshot.
Run from an installed project environment; choose fresh paths.

```python
from contextlib import closing
from pathlib import Path
from atp_lab.database.connection import open_writer, open_reader
from atp_lab.database.migrations import migrate
from atp_lab.database.identity import migrate_identity
from atp_lab.database.forecast import migrate_forecast
from atp_lab.database.schema_v4 import migrate_evaluation
from atp_lab.database.backup import backup_database, restore_database
from atp_lab.database.schema_v3 import verify_forecast_schema

root = Path("data/atp_lab")
root.mkdir(parents=True, exist_ok=True)
live = root / "synthetic.sqlite"
if live.exists():
    raise FileExistsError(live)
with closing(open_writer(live)) as writer:
    migrate(writer)
    migrate_identity(writer)
    migrate_forecast(writer)
    migrate_evaluation(writer)

saved = backup_database(live, root / "snapshot-001.sqlite")
recovered = restore_database(saved, root / "recovered-001.sqlite")
with closing(open_reader(recovered)) as reader:
    verify_forecast_schema(reader)
```

The source is read through SQLite's online backup API, not copied with a
raw filesystem copy. Committed WAL data is included and uncommitted
transactions are excluded. Concurrent commits may be included according
to SQLite snapshot semantics. No source checkpoint is requested.
The staged copy is converted to DELETE journal mode, verified against
the complete schema/marker, foreign_key_check and integrity_check, closed,
and reopened for verification. Publication uses a same-directory hard
link which cannot overwrite an existing target. Existing paths,
dangling symlinks and destination sidecars are rejected. Unsupported
filesystems fail closed; no destructive fallback. The backup callback
bounds retries to 30 seconds, subject to SQLite and OS call latency.
All handles close before publication; owned staging files are cleaned
on normal failure. A process crash may leave a private staging file.
Do not treat it as a published backup. No guarantee against power loss,
hostile concurrent directory changes or external file tampering.

Restore always creates a separate path. Keep the original and backup
until verification is complete. To use a recovered DB as a writer, close
its readers, stop any old worker, explicitly select the new path and
open_writer(recovered). Never overwrite a running DB or delete its WAL.
No automated recovery, rotation or scheduled backup is activated here.

## Evidence boundary

The database stores supplied metadata and local commitment digests.
S5 validates local synthetic prospective eligibility and scoring under
its typed single-writer contract; the database does not independently
establish timestamps, provider authenticity, real prestart eligibility,
settlement correctness or real model skill. S6-S8 remain separate gates.
Do not use synthetic results as real-world performance evidence.
