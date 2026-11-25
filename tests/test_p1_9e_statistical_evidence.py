"""P1.9e statistical evidence contracts; synthetic predictions only."""
import inspect
import math

import pytest

from atp_gate.tml_elo_experiment import _bootstrap, run_tml_elo_experiment
from scripts.p1_8c_cohort_research import run_replay
from test_tml_elo_experiment import season_files


def predictions(equal=False):
    return {year: [(f"{year}-{i}", 1, .8, .8 if equal else .6)
                   for i in range(4)] for year in (2023, 2024, 2025)}


def test_paired_surface_global_confidence_interval_same_resample():
    p = predictions()
    result = _bootstrap(list(p), p, replicates=50, seed=29)
    assert result["event_clusters"] == 12
    assert result["cluster_unit"] == "EVENT_ID"
    assert result["stratification"] == "EVENT_START_CALENDAR_YEAR"
    assert result["surface_elo_minus_global_elo_log_loss_95ci"] == pytest.approx(
        [math.log(.8/.6)]*2)
    assert result["surface_elo_minus_global_elo_brier_95ci"] == pytest.approx([.12]*2)


def test_equal_models_have_zero_paired_uncertainty():
    p = predictions(equal=True)
    result = _bootstrap(list(p), p, replicates=50, seed=29)
    assert result["surface_elo_minus_global_elo_log_loss_95ci"] == [0., 0.]
    assert result["surface_elo_minus_global_elo_brier_95ci"] == [0., 0.]


def test_insufficient_event_support_never_invents_interval():
    p = predictions()
    p[2023] = p[2023][:1]
    result = _bootstrap(list(p), p, replicates=50, seed=29)
    assert result["status"] == "INSUFFICIENT_EVENT_SUPPORT"
    assert result["surface_elo_minus_global_elo_log_loss_95ci"] is None
    assert result["surface_elo_minus_global_elo_brier_95ci"] is None


def test_seeded_paired_bootstrap_preserves_event_clusters():
    p = predictions()
    p[2023] += [("2023-0", 0, .7, .2)] * 4
    a = _bootstrap(list(p), p, replicates=50, seed=29)
    b = _bootstrap(list(p), p, replicates=50, seed=29)
    assert a == b
    assert a["event_clusters_by_year"] == {2023:4, 2024:4, 2025:4}
    assert a["replicates"] == 50
    assert a["surface_elo_minus_global_elo_log_loss_95ci"][0] < a["surface_elo_minus_global_elo_log_loss_95ci"][1]


def test_calendar_attribution_reconciles_source_season_and_fold(tmp_path):
    out = run_tml_elo_experiment(season_files(tmp_path), bootstrap_replicates=50)
    audit = out["calendar_attribution"]
    assert audit["cross_year_eligible_rows"] == 1
    assert audit["source_season_to_event_start_year"][2025] == {2024:1, 2025:4}
    assert audit["cross_year_evaluated_by_fold"] == {2023:0, 2024:1, 2025:0}
    assert sum(sum(v.values()) for v in audit["source_season_to_event_start_year"].values()) == out["source_match_rows_eligible"]
    assert out["evaluation_status"] == "PREVIOUSLY_INSPECTED_DEVELOPMENT_YEARS" or out["evaluation_status"] == "HISTORICAL_CALENDAR_EVALUATION_NOT_PROSPECTIVE"


def test_locked_replay_default_bootstrap_is_2000():
    assert inspect.signature(run_replay).parameters["bootstrap_replicates"].default == 2000
