from contextlib import closing
from dataclasses import replace
from hashlib import sha256

import pytest

from atp_lab.database import forecast, identity
from atp_lab.database.connection import open_writer
from atp_lab.database.forecast import migrate_forecast
from atp_lab.database.identity import migrate_identity
from atp_lab.database.migrations import migrate
from atp_lab.database.schema_v4 import migrate_evaluation
from atp_lab.database.schema_v5 import migrate_training
from atp_lab.dashboard.view import DashboardUnavailable, load_dashboard_view


def _database(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(open_writer(path)) as conn:
        migrate(conn)
        migrate_identity(conn)
        migrate_forecast(conn)
        migrate_evaluation(conn)
        migrate_training(conn)


def test_empty_synthetic_database_produces_consistent_six_page_snapshot(tmp_path):
    database = tmp_path / "data" / "synthetic.sqlite"
    _database(database)

    view = load_dashboard_view(database, mode="SYNTHETIC_DEMO")

    assert view.mode == "SYNTHETIC_DEMO"
    assert view.database_state == "READY"
    assert view.overview["fixtures"] == 0
    assert view.upcoming == ()
    assert view.tournaments == ()
    assert view.results == ()
    assert view.models["active_model_id"] is None
    assert view.health["real_data"] == "LOCKED"
    assert view.health["worker_state"] == "IDLE"


@pytest.mark.parametrize("mode", ["HISTORICAL", "SYNTHETIC_DEMO"])
def test_missing_database_is_a_visible_empty_state(tmp_path, mode):
    view = load_dashboard_view(tmp_path / "missing.sqlite", mode=mode)
    assert view.database_state == "MISSING"
    assert view.error_code == "DATABASE_MISSING"
    assert view.health["real_data"] == "LOCKED"


def test_unknown_dashboard_mode_fails_closed(tmp_path):
    with pytest.raises(ValueError, match="dashboard mode"):
        load_dashboard_view(tmp_path / "missing.sqlite", mode="REAL")


@pytest.mark.parametrize("fixture_state", ["CANCELLED", "POSTPONED"])
def test_upcoming_clearly_labels_cancelled_or_postponed_fixtures(tmp_path, fixture_state):
    from atp_lab.worker.demo import seed_demo

    database = tmp_path / "data" / "synthetic.sqlite"
    _database(database)
    seed_demo(database)
    observed = "2026-11-01T09:00:00Z"
    suffix = fixture_state.lower()
    snapshot = f"SYN-{suffix}-snapshot"
    with closing(open_writer(database)) as conn:
        conn.execute("BEGIN IMMEDIATE")
        identity.put_tournament(conn, identity.Tournament(
            f"SYN-{suffix}-tournament", f"SYN-{suffix}-event", "2027", "ATP250", "HARD"))
        identity.put_match(conn, identity.Match(
            f"SYN-{suffix}-match", f"SYN-{suffix}-tournament", "SYN-demo-A", "SYN-demo-C"))
        identity.put_snapshot(conn, identity.Snapshot(
            snapshot, "SYN-demo-feed", sha256(snapshot.encode()).hexdigest(), observed))
        identity.append_fixture(conn, identity.Fixture(
            f"SYN-{suffix}-fixture", f"SYN-{suffix}-match", 1, "SYN-demo-feed", snapshot,
            "SYN-demo-A", "SYN-demo-C", observed, observed,
            "2027-02-01T14:00:00Z", fixture_state))
        conn.commit()

    view = load_dashboard_view(database, mode="SYNTHETIC_DEMO")
    cancelled = next(row for row in view.upcoming if row["fixture_id"] == f"SYN-{suffix}-fixture")
    assert cancelled["state"] == fixture_state
    assert cancelled["forecast_state"] == fixture_state
    assert cancelled["probability_a"] is None


def test_upcoming_blocks_forecasts_when_match_has_multiple_fixture_sources(tmp_path):
    from atp_lab.worker.demo import seed_demo

    database = tmp_path / "data" / "synthetic.sqlite"
    _database(database)
    seed_demo(database)
    source_id = "SYN-second-feed"
    observed = "2026-11-02T09:00:00Z"
    snapshot = "SYN-second-feed-snapshot"
    with closing(open_writer(database)) as conn:
        conn.execute("BEGIN IMMEDIATE")
        identity.put_source(conn, identity.Source(source_id, "SYNTHETIC", "LOCKED"))
        match_id, player_a, player_b = conn.execute(
            "SELECT match_id,player_a,player_b FROM fixture_versions "
            "WHERE fixture_id='SYN-demo-fixture-upcoming'").fetchone()
        identity.put_snapshot(conn, identity.Snapshot(
            snapshot, source_id, sha256(snapshot.encode()).hexdigest(), observed))
        identity.append_fixture(conn, identity.Fixture(
            "SYN-second-source-fixture", match_id, 1, source_id, snapshot,
            player_a, player_b, observed, observed,
            "2027-01-20T14:00:00Z", "SCHEDULED"))
        conn.commit()

    view = load_dashboard_view(database, mode="SYNTHETIC_DEMO")
    rows = [row for row in view.upcoming if row["match_id"] == match_id]
    assert len(rows) == 2
    assert all(row["forecast_state"] == "AMBIGUOUS" for row in rows)
    assert all(row["probability_a"] is None for row in rows)


def test_legacy_predictions_and_evaluations_are_not_presented_as_verified(tmp_path):
    from atp_lab.worker.demo import seed_demo

    database = tmp_path / "data" / "synthetic.sqlite"
    _database(database)
    seed_demo(database)
    with closing(open_writer(database)) as conn:
        conn.execute("BEGIN IMMEDIATE")
        baseline = forecast.ModelVersion(*conn.execute(
            "SELECT model_id,model_digest,config_digest,training_cutoff,created_at,scope "
            "FROM model_versions WHERE model_id='SYN-global-elo-v1'").fetchone())
        legacy_model = replace(baseline, model_id="SYN-legacy-model")
        forecast.append_model(conn, legacy_model)
        prediction = conn.execute(
            "SELECT match_id,fixture_id,feature_id,created_at FROM predictions "
            "WHERE fixture_id='SYN-demo-fixture-scored'").fetchone()
        legacy_prediction = forecast.Prediction(
            "SYN-legacy-prediction", *prediction[:3], legacy_model.model_id,
            prediction[3], 0.6, "0" * 64)
        forecast.append_prediction(conn, legacy_prediction)
        forecast.append_evaluation(conn, forecast.Evaluation(
            "SYN-legacy-evaluation", legacy_prediction.prediction_id,
            "SYN-demo-result-scored", "2025-03-11T12:00:00Z", "RECORDED"))
        conn.commit()

    view = load_dashboard_view(database, mode="SYNTHETIC_DEMO")
    legacy = next(row for row in view.results if row["prediction_id"] == "SYN-legacy-prediction")
    assert legacy["commitment_state"] == "UNVERIFIED"
    assert legacy["status"] == "UNVERIFIED"
    assert legacy["reason"] == "NO_S5_RECEIPT"
    assert legacy["outcome_a"] is None
    assert view.overview["predictions"] == 3
    assert view.overview["scored"] == 2


def test_valid_commitment_with_unreceipted_assessment_is_not_scored(tmp_path):
    from atp_lab.worker.demo import seed_demo

    database = tmp_path / "data" / "synthetic.sqlite"
    _database(database)
    seed_demo(database)
    observed = "2025-03-12T17:00:00Z"
    snapshot = "SYN-corrected-result-snapshot"
    with closing(open_writer(database)) as conn:
        conn.execute("BEGIN IMMEDIATE")
        identity.put_snapshot(conn, identity.Snapshot(
            snapshot, "SYN-demo-feed", sha256(snapshot.encode()).hexdigest(), observed))
        identity.append_result(conn, identity.Result(
            "SYN-demo-result-correction", "SYN-demo-match-scored", 2,
            "SYN-demo-feed", snapshot, observed, "2025-03-12T18:00:00Z",
            "2025-03-12T16:00:00Z", "2025-03-10T14:00:00Z", "COMPLETED", "SYN-demo-C"))
        prediction_id = conn.execute(
            "SELECT prediction_id FROM predictions WHERE fixture_id='SYN-demo-fixture-scored'"
        ).fetchone()[0]
        forecast.append_evaluation(conn, forecast.Evaluation(
            "SYN-unreceipted-assessment", prediction_id,
            "SYN-demo-result-correction", "2025-03-13T12:00:00Z", "RECORDED"))
        conn.commit()

    view = load_dashboard_view(database, mode="SYNTHETIC_DEMO")
    corrected = next(row for row in view.results
                     if row["result_id"] is None and row["reason"] == "INVALID_ASSESSMENT_RECEIPT")
    assert corrected["commitment_state"] == "VERIFIED"
    assert corrected["status"] == "UNVERIFIED"
    assert corrected["outcome_a"] is None


def test_results_marks_assessment_historical_after_later_result_revision(tmp_path):
    from atp_lab.worker.demo import seed_demo

    database = tmp_path / "data" / "synthetic.sqlite"
    _database(database)
    seed_demo(database)
    observed = "2025-04-01T12:00:00Z"
    snapshot = "SYN-later-result-revision-snapshot"
    with closing(open_writer(database)) as conn:
        conn.execute("BEGIN IMMEDIATE")
        identity.put_snapshot(conn, identity.Snapshot(
            snapshot, "SYN-demo-feed", sha256(snapshot.encode()).hexdigest(), observed))
        identity.append_result(conn, identity.Result(
            "SYN-demo-result-revision-2", "SYN-demo-match-scored", 2,
            "SYN-demo-feed", snapshot, observed, None,
            None, None, "UNKNOWN", None))
        conn.commit()

    view = load_dashboard_view(database, mode="SYNTHETIC_DEMO")
    recorded = next(row for row in view.results if row["result_id"] == "SYN-demo-result-scored")
    assert recorded["status"] == "RECORDED"
    assert recorded["assessment_label"] == "RECORDED (HISTORICAL)"
    assert recorded["result_revision"] == 1
    assert recorded["latest_result_revision"] == 2
    assert recorded["latest_result_state"] == "PENDING"


def test_invalid_model_lifecycle_chain_is_not_shown_as_active(tmp_path):
    from atp_lab.worker.demo import seed_demo

    database = tmp_path / "data" / "synthetic.sqlite"
    _database(database)
    seed_demo(database)
    with closing(open_writer(database)) as conn:
        conn.execute("BEGIN IMMEDIATE")
        baseline = forecast.ModelVersion(*conn.execute(
            "SELECT model_id,model_digest,config_digest,training_cutoff,created_at,scope "
            "FROM model_versions WHERE model_id='SYN-global-elo-v1'").fetchone())
        rogue = replace(baseline, model_id="SYN-rogue-model")
        forecast.append_model(conn, rogue)
        conn.execute(
            "INSERT INTO model_lifecycle_events VALUES (?,?,?,?,?,?,?,?,?)",
            ("SYN-rogue-event", 1, "SYN-rogue-approval", "PROMOTE", baseline.model_id,
             rogue.model_id, "2025-03-01T00:00:00Z", "{}", "0" * 64))
        conn.commit()

    view = load_dashboard_view(database, mode="SYNTHETIC_DEMO")
    assert view.models["active_model_id"] is None
    assert view.models["selection_state"] == "UNVERIFIED"
