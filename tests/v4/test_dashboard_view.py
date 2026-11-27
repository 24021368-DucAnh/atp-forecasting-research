from contextlib import closing

import pytest

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
