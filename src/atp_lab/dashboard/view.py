"""Consistent read-only dashboard snapshots for the six local pages."""

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from atp_lab.database.connection import open_reader
from atp_lab.database.schema_v3 import verify_forecast_schema
from atp_lab.prediction.inference import MODEL_ID
from atp_lab.worker.lease import read_lease

MODES = ("HISTORICAL", "SYNTHETIC_DEMO")


class DashboardUnavailable(ValueError):
    """The local database cannot be safely shown by the dashboard."""


@dataclass(frozen=True)
class DashboardView:
    mode: str
    database_state: str
    error_code: str | None
    overview: dict
    upcoming: tuple[dict, ...]
    tournaments: tuple[dict, ...]
    results: tuple[dict, ...]
    models: dict
    health: dict


def _empty(mode: str, state: str, error: str | None = None) -> DashboardView:
    return DashboardView(
        mode, state, error,
        {"fixtures": 0, "predictions": 0, "scored": 0}, (), (), (),
        {"active_model_id": None, "candidates": (), "protocols": 0},
        {"real_data": "LOCKED", "worker_state": "IDLE",
         "last_job": None, "quality_issues": 0, "database_version": None},
    )


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                        (name,)).fetchone() is not None


def _snapshot(conn: sqlite3.Connection, data_dir: Path, mode: str) -> DashboardView:
    verify_forecast_schema(conn)
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    overview = {
        "fixtures": conn.execute("SELECT count(*) FROM fixture_versions").fetchone()[0],
        "predictions": conn.execute("SELECT count(*) FROM predictions").fetchone()[0],
        "scored": conn.execute("SELECT count(*) FROM evaluations WHERE status='RECORDED'").fetchone()[0],
    }
    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    upcoming_rows = conn.execute(
        "SELECT f.fixture_id,f.match_id,f.revision,f.scheduled_start,f.state,"
        "m.canonical_a,m.canonical_b,t.event_key,t.edition,t.tier,t.surface,"
        "p.model_id,p.probability_a,p.created_at "
        "FROM fixture_versions f JOIN matches m ON m.match_id=f.match_id "
        "JOIN tournaments t ON t.tournament_id=m.tournament_id "
        "LEFT JOIN predictions p ON p.fixture_id=f.fixture_id "
        "WHERE f.revision=(SELECT max(x.revision) FROM fixture_versions x "
        "WHERE x.match_id=f.match_id AND x.source_id=f.source_id) "
        "AND f.state IN ('SCHEDULED','CANCELLED','POSTPONED') AND f.scheduled_start>=? "
        "ORDER BY f.scheduled_start,f.match_id LIMIT 500", (now,)).fetchall()
    upcoming = tuple({
        "fixture_id": r[0], "match_id": r[1], "revision": r[2],
        "scheduled_start_utc": r[3], "state": r[4],
        "player_a": r[5], "player_b": r[6], "event": r[7], "edition": r[8],
        "tier": r[9], "surface": r[10], "model_id": r[11],
        "probability_a": r[12] if r[11] is not None else None,
        "forecast_at": r[13],
        "forecast_state": ("COMMITTED" if r[11] is not None else "NO_FORECAST"),
    } for r in upcoming_rows)
    tournament_rows = conn.execute(
        "SELECT t.tournament_id,t.event_key,t.edition,t.tier,t.surface,count(DISTINCT m.match_id) "
        "FROM tournaments t LEFT JOIN matches m ON m.tournament_id=t.tournament_id "
        "GROUP BY t.tournament_id,t.event_key,t.edition,t.tier,t.surface "
        "ORDER BY t.edition DESC,t.event_key LIMIT 500").fetchall()
    tournaments = tuple({
        "tournament_id": r[0], "event": r[1], "edition": r[2], "tier": r[3],
        "surface": r[4], "match_count": r[5],
    } for r in tournament_rows)
    result_rows = conn.execute(
        "SELECT p.prediction_id,p.match_id,p.fixture_id,p.model_id,p.created_at,"
        "p.probability_a,p.commitment_digest,e.result_id,e.evaluated_at,e.status,"
        "a.reason,a.outcome_a,r.revision,r.state,t.event_key,t.edition,m.canonical_a,m.canonical_b "
        "FROM predictions p LEFT JOIN evaluations e ON e.prediction_id=p.prediction_id "
        "LEFT JOIN matches m ON m.match_id=p.match_id "
        "LEFT JOIN tournaments t ON t.tournament_id=m.tournament_id "
        "LEFT JOIN assessment_receipts a ON a.evaluation_id=e.evaluation_id "
        "LEFT JOIN result_versions r ON r.result_id=e.result_id "
        "ORDER BY p.created_at DESC,e.evaluated_at DESC LIMIT 1000").fetchall()
    results = tuple({
        "prediction_id": r[0], "match_id": r[1], "fixture_id": r[2],
        "model_id": r[3], "created_at": r[4], "probability_a": r[5],
        "commitment_digest": r[6], "result_id": r[7], "evaluated_at": r[8],
        "status": r[9] or "PENDING", "reason": r[10] or "NOT_EVALUATED",
        "outcome_a": r[11], "result_revision": r[12], "result_state": r[13],
        "event": r[14], "edition": r[15], "player_a": r[16], "player_b": r[17],
    } for r in result_rows)
    model_rows = conn.execute(
        "SELECT model_id,scope,training_cutoff,created_at,model_digest,config_digest "
        "FROM model_versions ORDER BY created_at,model_id").fetchall()
    active_model = MODEL_ID
    if _table_exists(conn, "model_lifecycle_events"):
        row = conn.execute(
            "SELECT to_model_id FROM model_lifecycle_events ORDER BY rowid DESC LIMIT 1").fetchone()
        if row is not None:
            active_model = row[0]
    models = {
        "active_model_id": active_model if any(r[0] == active_model for r in model_rows) else None,
        "versions": tuple({"model_id": r[0], "scope": r[1], "training_cutoff": r[2],
                           "created_at": r[3], "model_digest": r[4], "config_digest": r[5]}
                          for r in model_rows),
        "candidates": tuple(r[0] for r in model_rows if r[0] != MODEL_ID),
        "protocols": (conn.execute("SELECT count(*) FROM training_protocols").fetchone()[0]
                      if _table_exists(conn, "training_protocols") else 0),
    }
    last_job = None
    if _table_exists(conn, "job_runs"):
        row = conn.execute(
            "SELECT job_id,kind,started_at,ended_at,status FROM job_runs "
            "ORDER BY ended_at DESC,job_id DESC LIMIT 1").fetchone()
        if row is not None:
            last_job = dict(zip(("job_id", "kind", "started_at", "ended_at", "status"), row))
    quality = (conn.execute("SELECT count(*) FROM data_quality_issues").fetchone()[0]
               if _table_exists(conn, "data_quality_issues") else 0)
    lease = read_lease(data_dir)
    return DashboardView(
        mode, "READY", None, overview, upcoming, tournaments, results, models,
        {"real_data": "LOCKED", "worker_state": lease.state,
         "last_worker_id": lease.worker_id, "last_job": last_job,
         "quality_issues": quality, "database_version": version},
    )


def load_dashboard_view(path: Path, *, mode: str = "SYNTHETIC_DEMO") -> DashboardView:
    """Load a bounded consistent snapshot through SQLite's read-only URI."""
    if type(mode) is not str or mode not in MODES:
        raise ValueError("unsupported dashboard mode")
    database = Path(path)
    if not database.exists():
        return _empty(mode, "MISSING", "DATABASE_MISSING")
    if not database.is_file() or database.is_symlink():
        return _empty(mode, "UNAVAILABLE", "DATABASE_PATH_UNSAFE")
    try:
        with closing(open_reader(database)) as conn:
            conn.execute("BEGIN")
            try:
                view = _snapshot(conn, database.parent, mode)
                conn.commit()
                return view
            except BaseException:
                conn.rollback()
                raise
    except (sqlite3.DatabaseError, OSError, ValueError) as exc:
        raise DashboardUnavailable("local database failed read-only verification") from exc
