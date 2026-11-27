"""Consistent read-only dashboard snapshots for the six local pages."""

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from datetime import datetime, timezone

from atp_lab.database.connection import open_reader
from atp_lab.database.identity import utc_timestamp
from atp_lab.database.schema_v3 import verify_forecast_schema
from atp_lab.evaluation.eligibility import decide
from atp_lab.evaluation.service import _stored_assessment
from atp_lab.prediction.commitment import UnverifiedCommitment, _get_commitment
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


def _verified_commitment(conn: sqlite3.Connection, prediction_id: str):
    try:
        return _get_commitment(conn, prediction_id), None
    except UnverifiedCommitment:
        return None, "NO_S5_RECEIPT"
    except (OSError, sqlite3.DatabaseError, TypeError, ValueError):
        return None, "INVALID_S5_RECEIPT"


def _verified_assessment(conn: sqlite3.Connection, *, prediction_id: str,
                         commitment, evaluation_id: str, result_id: str,
                         evaluated_at: str, stored_status: str):
    try:
        decision = decide(conn, commitment, evaluated_at)
        assessment = _stored_assessment(conn, prediction_id, decision, evaluated_at)
    except (OSError, sqlite3.DatabaseError, TypeError, ValueError):
        return None
    if (assessment is None or assessment.evaluation_id != evaluation_id
            or assessment.result_id != result_id or assessment.evaluated_at != evaluated_at
            or assessment.status != stored_status):
        return None
    return assessment


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
        "p.prediction_id,p.model_id,p.probability_a,p.created_at "
        "FROM fixture_versions f JOIN matches m ON m.match_id=f.match_id "
        "JOIN tournaments t ON t.tournament_id=m.tournament_id "
        "LEFT JOIN predictions p ON p.fixture_id=f.fixture_id "
        "WHERE f.revision=(SELECT max(x.revision) FROM fixture_versions x "
        "WHERE x.match_id=f.match_id AND x.source_id=f.source_id) "
        "AND f.state IN ('SCHEDULED','CANCELLED','POSTPONED') AND f.scheduled_start>=? "
        "ORDER BY f.scheduled_start,f.match_id LIMIT 500", (now,)).fetchall()
    upcoming_rows_view = []
    for r in upcoming_rows:
        if r[4] in ("CANCELLED", "POSTPONED"):
            prediction_state, model_id, probability, forecast_at = r[4], None, None, None
        elif r[11] is None:
            prediction_state, model_id, probability, forecast_at = "NO_FORECAST", None, None, None
        else:
            commitment, _ = _verified_commitment(conn, r[11])
            if commitment is None:
                prediction_state, model_id, probability, forecast_at = "UNVERIFIED", None, None, None
            else:
                prediction_state = "COMMITTED"
                model_id = commitment.prediction.model_id
                probability = commitment.prediction.probability_a
                forecast_at = commitment.prediction.created_at
        upcoming_rows_view.append({
            "fixture_id": r[0], "match_id": r[1], "revision": r[2],
            "scheduled_start_utc": r[3], "state": r[4],
            "player_a": r[5], "player_b": r[6], "event": r[7], "edition": r[8],
            "tier": r[9], "surface": r[10], "model_id": model_id,
            "probability_a": probability, "forecast_at": forecast_at,
            "forecast_state": prediction_state,
        })
    upcoming = tuple(upcoming_rows_view)
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
        "p.probability_a,p.commitment_digest,e.evaluation_id,e.result_id,e.evaluated_at,e.status,"
        "a.reason,a.outcome_a,r.revision,r.state,t.event_key,t.edition,m.canonical_a,m.canonical_b "
        "FROM predictions p LEFT JOIN evaluations e ON e.prediction_id=p.prediction_id "
        "LEFT JOIN matches m ON m.match_id=p.match_id "
        "LEFT JOIN tournaments t ON t.tournament_id=m.tournament_id "
        "LEFT JOIN assessment_receipts a ON a.evaluation_id=e.evaluation_id "
        "LEFT JOIN result_versions r ON r.result_id=e.result_id "
        "ORDER BY p.created_at DESC,e.evaluated_at DESC LIMIT 1000").fetchall()
    match_ids = sorted({r[1] for r in result_rows if r[1] is not None})
    latest_result_rows = []
    if match_ids:
        placeholders = ",".join("?" for _ in match_ids)
        latest_result_rows = conn.execute(
            "WITH heads AS ("
            "SELECT match_id,MAX(revision) AS revision,COUNT(DISTINCT source_id) AS sources "
            f"FROM result_versions WHERE match_id IN ({placeholders}) GROUP BY match_id), ranked AS ("
            "SELECT match_id,result_id,state,revision,available_at,ROW_NUMBER() OVER ("
            "PARTITION BY match_id ORDER BY revision DESC,result_id) AS position "
            f"FROM result_versions WHERE match_id IN ({placeholders})) "
            "SELECT h.match_id,h.revision,h.sources,r.result_id,r.state,r.available_at "
            "FROM heads h JOIN ranked r ON r.match_id=h.match_id AND r.position=1",
            [*match_ids, *match_ids]).fetchall()
    now = utc_timestamp(datetime.now(timezone.utc).isoformat())
    latest_results = {
        r[0]: (r[1], None if r[2] > 1 else r[3],
               "AMBIGUOUS" if r[2] > 1 else
               "PENDING" if r[5] is None or utc_timestamp(r[5]) > now else r[4])
        for r in latest_result_rows
    }
    results_view = []
    for r in result_rows:
        latest_result = latest_results.get(r[1])
        latest_revision = latest_result[0] if latest_result else None
        latest_result_id = latest_result[1] if latest_result else None
        latest_state = latest_result[2] if latest_result else None
        commitment, commitment_error = _verified_commitment(conn, r[0])
        if commitment is None:
            commitment_state = "UNVERIFIED"
            status, reason, outcome = "UNVERIFIED", commitment_error, None
            result_id, evaluated_at, result_revision, result_state = None, None, None, None
            probability, digest = None, None
        else:
            commitment_state = "VERIFIED"
            probability = commitment.prediction.probability_a
            digest = commitment.prediction.commitment_digest
            if r[7] is None:
                status, reason, outcome = "PENDING", "NOT_EVALUATED", None
                result_id, evaluated_at, result_revision, result_state = None, None, None, None
            else:
                assessment = _verified_assessment(
                    conn, prediction_id=r[0], commitment=commitment,
                    evaluation_id=r[7], result_id=r[8], evaluated_at=r[9], stored_status=r[10])
                if assessment is None:
                    status, reason, outcome = "UNVERIFIED", "INVALID_ASSESSMENT_RECEIPT", None
                    result_id, evaluated_at, result_revision, result_state = None, None, None, None
                else:
                    status, reason, outcome = assessment.status, assessment.reason, assessment.outcome_a
                    result_id, evaluated_at, result_revision, result_state = r[8], r[9], r[13], r[14]
        results_view.append({
            "prediction_id": r[0], "match_id": r[1], "fixture_id": r[2],
            "model_id": commitment.prediction.model_id if commitment else r[3],
            "created_at": r[4], "probability_a": probability,
            "commitment_digest": digest, "commitment_state": commitment_state,
            "result_id": result_id, "evaluated_at": evaluated_at,
            "status": status, "reason": reason, "outcome_a": outcome,
            "result_revision": result_revision, "result_state": result_state,
            "assessment_label": (f"{status} (HISTORICAL)"
                                 if result_id is not None and result_id != latest_result_id
                                 else status),
            "latest_result_revision": latest_revision,
            "latest_result_state": latest_state,
            "event": r[15], "edition": r[16], "player_a": r[17], "player_b": r[18],
        })
    results = tuple(results_view)
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
