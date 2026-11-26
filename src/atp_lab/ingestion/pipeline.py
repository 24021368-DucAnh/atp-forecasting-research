"""Atomic offline ingestion; no real transport or scheduler."""
from dataclasses import dataclass, fields
from typing import Callable
import re
import sqlite3

from atp_lab.database import identity, forecast
from atp_lab.database.migrations import _transaction
from atp_lab.database.schema_v2 import require_writer
from atp_lab.database.schema_v3 import verify_forecast_schema
from . import adapter, parser

_SYN_ID = re.compile(r"SYN-[A-Za-z0-9._:-]+")
_OBSERVATION_FIELDS = {"snapshot_id", "observed_at", "available_at"}


@dataclass(frozen=True)
class IngestReport:
    status: str
    reason: str | None
    inserted: int
    replayed: int
    snapshot_id: str | None


class _RevisionConflict(ValueError):
    """Existing immutable revision conflicts with a new observation."""


def _require_new_job(conn: sqlite3.Connection, job_id: str) -> None:
    if conn.execute("SELECT 1 FROM job_runs WHERE job_id=?", (job_id,)).fetchone():
        raise ValueError("terminal job ID already exists")


def _registered_source(conn: sqlite3.Connection, policy: adapter.SourcePolicy) -> bool:
    if (type(policy) is not adapter.SourcePolicy
            or type(policy.source_id) is not str
            or _SYN_ID.fullmatch(policy.source_id) is None):
        return False
    row = conn.execute(
        "SELECT mode, permission_status FROM data_sources WHERE source_id=?",
        (policy.source_id,),
    ).fetchone()
    return row is not None and tuple(row) == ("SYNTHETIC", "LOCKED")


def _write_job(conn, job_id, started, ended, status) -> None:
    forecast.record_job(conn, forecast.JobRun(
        job_id, "INGEST", 1, started, ended, status))


def _terminal_failure(conn, policy, job_id, started, observed, ended,
                      status, reason) -> IngestReport:
    # This transaction begins only after any failed data transaction rolled back.
    with _transaction(conn):
        verify_forecast_schema(conn)
        _require_new_job(conn, job_id)
        _write_job(conn, job_id, started, ended, status)
        if status == "FAILED":
            if not _registered_source(conn, policy):
                raise ValueError("synthetic source no longer registered")
            forecast.record_quality_issue(conn, forecast.QualityIssue(
                parser._stable_id("quality", job_id), policy.source_id,
                observed, reason))
    return IngestReport(status, reason, 0, 0, None)


def _append_or_replay(conn: sqlite3.Connection,
                      record: identity.Fixture | identity.Result) -> bool:
    if type(record) is identity.Fixture:
        table, append = "fixture_versions", identity.append_fixture
    elif type(record) is identity.Result:
        table, append = "result_versions", identity.append_result
    else:
        raise TypeError("unexpected normalized record")
    names = tuple(field.name for field in fields(record))
    stored = conn.execute(
        f"SELECT {', '.join(names)} FROM {table} "
        "WHERE match_id=? AND source_id=? AND revision=?",
        (record.match_id, record.source_id, record.revision),
    ).fetchone()
    if stored is None:
        return append(conn, record)
    old = dict(zip(names, stored))
    new = {name: getattr(record, name) for name in names}
    if old == new:
        return False
    same_provider_fields = all(old[name] == new[name] for name in names
                               if name not in _OBSERVATION_FIELDS)
    if same_provider_fields and new["observed_at"] > old["observed_at"]:
        # Retain the first receipt and availability, never rewrite lineage.
        return False
    raise _RevisionConflict("immutable revision conflict")


def ingest_batch(conn: sqlite3.Connection, policy: adapter.SourcePolicy,
                 url: str, transport: adapter.SyntheticTransport, *,
                 job_id: str, started_at: str, observed_at: str,
                 available_at: str | None, ended_at: str,
                 sleep: Callable[[float], None]) -> IngestReport:
    """Execute one bounded synthetic batch on an idle trusted writer.

    Clocks and transport are caller-provided synthetic inputs. The job is
    an invocation receipt, not a durable claim or worker lease. The single
    writer contract excludes concurrent orchestrators. Operational errors
    propagate without fabricated success or data-quality receipts.
    """
    if conn.in_transaction:
        raise ValueError("ingestion requires an idle writer")
    require_writer(conn)
    verify_forecast_schema(conn)
    if type(job_id) is not str or _SYN_ID.fullmatch(job_id) is None:
        raise ValueError("invalid synthetic job ID")
    started = identity.utc_timestamp(started_at)
    observed = identity.utc_timestamp(observed_at)
    ended = identity.utc_timestamp(ended_at)
    available = (None if available_at is None
                 else identity.utc_timestamp(available_at))
    if (not started <= observed <= ended
            or (available is not None and not observed <= available <= ended)):
        raise ValueError("invalid synthetic job clock order")
    _require_new_job(conn, job_id)

    try:
        adapter._check_policy(policy, url)
        if not _registered_source(conn, policy):
            raise adapter.FetchBlocked("synthetic source not registered")
        receipt = adapter.fetch_synthetic(policy, url, transport, sleep=sleep)
    except adapter.FetchBlocked:
        return _terminal_failure(conn, policy, job_id, started, observed,
                                 ended, "BLOCKED", "FETCH_BLOCKED")
    except adapter.TransientFetchError:
        return _terminal_failure(conn, policy, job_id, started, observed,
                                 ended, "FAILED", "FETCH_TRANSIENT_EXHAUSTED")
    except adapter.PermanentFetchError:
        return _terminal_failure(conn, policy, job_id, started, observed,
                                 ended, "FAILED", "FETCH_PERMANENT")
    except adapter.InvalidPayload:
        return _terminal_failure(conn, policy, job_id, started, observed,
                                 ended, "FAILED", "INVALID_PAYLOAD")

    try:
        with _transaction(conn):
            verify_forecast_schema(conn)
            _require_new_job(conn, job_id)
            if not _registered_source(conn, policy):
                raise ValueError("synthetic source no longer registered")
            batch = parser.parse_batch(conn, receipt, observed_at=observed,
                                       available_at=available)
            identity.put_snapshot(conn, batch.snapshot)
            inserted = replayed = 0
            for record in (*batch.fixtures, *batch.results):
                if _append_or_replay(conn, record):
                    inserted += 1
                else:
                    replayed += 1
            _write_job(conn, job_id, started, ended, "SUCCEEDED")
        return IngestReport("SUCCEEDED", None, inserted, replayed,
                            batch.snapshot.snapshot_id)
    except parser.ParseError:
        reason = "PARSE_REJECTED"
    except _RevisionConflict:
        reason = "REVISION_CONFLICT"
    return _terminal_failure(conn, policy, job_id, started, observed,
                             ended, "FAILED", reason)
