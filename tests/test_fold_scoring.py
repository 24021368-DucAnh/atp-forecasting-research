"""Synthetic-only chronological ATP forecast-score audit contracts."""
from copy import deepcopy
from math import log

import pytest

from atp_gate.fold_scoring import audit_fold_scores


def sample_folds():
    folds = []
    for year in (2022, 2023, 2024):
        rows = []
        for event_idx in (1, 2):
            for match_idx in (1, 2):
                rows.append({
                    "match_id": f"{year}-event{event_idx}-match{match_idx}",
                    "event_id": f"ATP_{year}_EVENT{event_idx}",
                    "date": f"{year}-07-10",
                    "outcome_a": 1,
                    "p_market": 0.5,
                    "p_elo": 0.6,
                    "p_xgb": 0.8,
                    "tier": "ATP_500",
                    "surface": "HARD",
                })
        folds.append({
            "train_end": f"{year-1}-12-31",
            "calibrate_start": f"{year}-01-01",
            "calibrate_end": f"{year}-03-31",
            "test_start": f"{year}-07-01",
            "test_end": f"{year}-07-31",
            "rows": rows,
        })
    return folds


def test_identical_matched_rows_are_scored_with_correct_loss():
    report = audit_fold_scores(sample_folds(), bootstrap_replicates=50, seed=7)
    assert report["status"] == "UNTRUSTED_FORECAST_EVALUATION_ONLY"
    assert report["fold_count"] == 3
    assert report["matched_test_n"] == 12
    assert report["aggregate"]["market_brier"] == pytest.approx(0.25)
    assert report["aggregate"]["elo_brier"] == pytest.approx(0.16)
    assert report["aggregate"]["xgb_brier"] == pytest.approx(0.04)
    assert report["aggregate"]["market_log_loss"] == pytest.approx(-log(0.5))
    assert report["aggregate"]["xgb_log_loss"] == pytest.approx(-log(0.8))
    assert report["aggregate"]["xgb_minus_market_log_loss"] == pytest.approx(log(0.5/0.8))
    assert report["eligible_for_model_training"] == 0
    assert report["market_edge_verified"] is False
    assert report["allocation_enabled"] is False and report["stake"] == 0


def test_cluster_bootstrap_is_seeded_and_flags_short_cluster_sets():
    a = audit_fold_scores(sample_folds(), bootstrap_replicates=60, seed=101)
    b = audit_fold_scores(sample_folds(), bootstrap_replicates=60, seed=101)
    assert a["paired_uncertainty"] == b["paired_uncertainty"]
    assert a["paired_uncertainty"]["status"] == "CLUSTER_BOOTSTRAP_DESCRIPTIVE_ONLY"
    assert a["paired_uncertainty"]["unique_event_clusters"] == 6
    small = sample_folds()
    for fold in small:
        fold["rows"] = fold["rows"][:2]
    c = audit_fold_scores(small, bootstrap_replicates=60, seed=101)
    assert c["paired_uncertainty"]["status"] == "INSUFFICIENT_CLUSTER_SUPPORT"
    assert c["paired_uncertainty"]["xgb_minus_market_95ci"] is None


def test_no_implicit_sample_differences_with_missing_market_row():
    folds = sample_folds()
    del folds[0]["rows"][0]["p_market"]
    with pytest.raises(ValueError):
        audit_fold_scores(folds)


def test_duplicate_match_across_two_folds_is_rejected():
    folds = sample_folds()
    folds[1]["rows"][0]["match_id"] = folds[0]["rows"][0]["match_id"]
    with pytest.raises(ValueError):
        audit_fold_scores(folds)


def test_fold_requires_disjoint_train_calibration_and_test():
    folds = sample_folds()
    folds[0]["train_end"] = "2022-01-01"
    with pytest.raises(ValueError):
        audit_fold_scores(folds)


def test_overlapping_holdout_windows_rejected():
    folds = sample_folds()
    folds[1]["test_start"] = "2022-07-20"
    with pytest.raises(ValueError):
        audit_fold_scores(folds)


@pytest.mark.parametrize("alter", [
    lambda f: f[0]["rows"][0].update(outcome_a=True),
    lambda f: f[0]["rows"][0].update(outcome_a=2),
    lambda f: f[0]["rows"][0].update(p_xgb=1),
    lambda f: f[0]["rows"][0].update(p_market=float("nan")),
    lambda f: f[0]["rows"][0].update(date="2022-03-01"),
    lambda f: f[0]["rows"][0].update(tier="ATP_250"),
])
def test_bad_outcomes_probabilities_dates_and_scope_refused(alter):
    folds = sample_folds()
    alter(folds)
    with pytest.raises(ValueError):
        audit_fold_scores(folds)


def test_fewer_than_three_folds_is_insufficient():
    with pytest.raises(ValueError):
        audit_fold_scores(sample_folds()[:2])


def test_zero_event_provenance_rejected():
    folds = sample_folds()
    folds[0]["rows"][0]["event_id"] = ""
    with pytest.raises(ValueError):
        audit_fold_scores(folds)
