# S2 Task 1 - SQLite bootstrap implementation plan

> For agentic workers: use superpowers:executing-plans and test-driven-development.

Goal: file-backed offline SQLite connection and transactional migration foundation.
Architecture: stdlib sqlite3 only; connection.py owns open policies,
migrations.py owns schema version and transaction boundaries. No ingestion,
data permissions, worker, UI wiring, or production DB.
Spec: docs/superpowers/specs/2026-11-26-v4-local-dashboard-design.md.
Plan authority: issue #61; accepted S1 main 288a720a513591c5dafb61be0bd669ab53caa925.
Global constraints: synthetic fixtures in temporary paths only; no runtime DB
tracked, preserve V3 engine/evidence/permissions and existing core CI.
Review focus: read-only URI with path escaping, FK per connection, WAL,
version mismatch, pre-existing v0 schema, caller-owned transactions, real
DDL rollback. Eight tests in tests/v4/test_database_bootstrap.py.

- [ ] RED: commit only tests and plan, verify eight intended missing-module
  failures on core CI. Existing 657 tests must still pass.
- [ ] GREEN: src/atp_lab/database/__init__.py, connection.py, migrations.py.
  open_writer(path: Path) -> sqlite3.Connection: WAL, FK ON, timeout 5000ms;
  explicit transaction control (isolation_level=None); caller closes handle.
  open_reader(path: Path) -> sqlite3.Connection: resolved file URI mode=ro,
  query_only ON, FK ON, timeout; no implicit file creation; close on setup
  failure. Use Path.as_uri() for special characters.
  apply_migration(conn, expected_version: int, target_version: int,
  statements: tuple[str, ...]) -> int: internal trusted SQL only; reject
  active caller transaction and invalid version step; BEGIN IMMEDIATE,
  read version inside transaction; execute statements individually (not
  executescript), set user_version, commit or roll back on any exception.
  migrate(conn) -> int: reject unknown versions and nonempty v0; v1
  bootstrap marker only (no application tables); use same migration
  transaction to guard empty-schema check. Reject forged or unrecognized
  v1 marker. Idempotent v1. Caller must not supply untrusted SQL.
- [ ] Verify targeted and full core CI, mandatory separate UI CI, manifest.
  No application tables until Task 2. v1 remains unreleased until S2
  accepted, so schema can be extended within S2 migration atomically;
  Task 2 must explicitly test any bootstrap-only v1 database upgrade, or
  bump version if needed. Do not silently accept missing tables.

Ruling: main merge tree equals approved S1 HEAD; post-merge CI must be
verified before treating main as fully regression-certified. Isolated RED
branch preparation is safe meanwhile. Minor S1 follow-ups from receipt
7186940795 are deferred to a separate bounded task, not silently fixed
during bootstrap. No merge without explicit exact-head owner authorization.
