"""Regression contract for P2.4 repeated bootstrap evidence."""
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from atp_gate import tml_ablation

ROOT = Path(__file__).resolve().parents[1]


def compare(previous, current):
    fn = getattr(tml_ablation, "compare_repeated_models", None)
    assert callable(fn), "P2.4 repeat comparison must expose bootstrap endpoints"
    return fn(previous, current)


def archived_models(phase):
    name = {3: "p2_3_fixed_ml", 4: "p2_4_fixed_ablation"}[phase]
    path = ROOT / "docs" / "research" / f"{name}_evidence_20261125.json"
    return json.loads(path.read_text(encoding="utf-8"))["result"]["evaluation"]["models"]


def test_repeat_comparison_reports_all_archived_endpoints():
    previous, current = archived_models(3), archived_models(4)
    result = compare(previous, current)
    assert set(result) == set(previous)
    assert result["global_elo"]["bootstrap_endpoint_differences"] is None
    for name in previous.keys() - {"global_elo"}:
        row = result[name]
        differences = row["bootstrap_endpoint_differences"]
        assert set(differences) == {"log_loss_95ci", "brier_95ci"}
        for metric, endpoints in differences.items():
            old = previous[name]["minus_global_elo"][metric]
            new = current[name]["minus_global_elo"][metric]
            assert endpoints == pytest.approx([new[0] - old[0], new[1] - old[1]], abs=1e-15)
        assert row["max_abs_bootstrap_endpoint_difference"] == pytest.approx(
            max(abs(x) for pair in differences.values() for x in pair), abs=1e-15
        )


@pytest.mark.parametrize("bad", [None, [], [0.0], [0.0, 1.0, 2.0], [float("nan"), 1.0], [2.0, 1.0]])
def test_repeat_comparison_rejects_malformed_endpoints(bad):
    previous, current = archived_models(3), archived_models(4)
    current["logistic_platt"]["minus_global_elo"]["log_loss_95ci"] = bad
    with pytest.raises(ValueError):
        compare(previous, current)


def test_repeat_comparison_rejects_missing_model():
    previous, current = archived_models(3), archived_models(4)
    del current["logistic_platt"]
    with pytest.raises(ValueError):
        compare(previous, current)


def test_repeat_comparison_rejects_mismatched_fold_support():
    previous, current = archived_models(3), archived_models(4)
    current["logistic_platt"]["folds"].pop()
    with pytest.raises(ValueError):
        compare(previous, current)


@pytest.mark.parametrize("target", ["previous", "current", "model", "fold"])
def test_repeat_comparison_rejects_non_mapping(target):
    previous, current = archived_models(3), archived_models(4)
    if target == "previous":
        previous = None
    elif target == "current":
        current = []
    elif target == "model":
        current["logistic_platt"] = None
    else:
        current["logistic_platt"]["folds"][0] = None
    with pytest.raises(ValueError):
        compare(previous, current)


@pytest.mark.parametrize("defect", ["empty", "missing_seed", "missing_replicates",
                                   "missing_semantics", "blank_semantics",
                                   "boolean_seed", "mismatch", "semantics_mismatch"])
def test_repeat_comparison_rejects_invalid_bootstrap_contract(defect):
    previous, current = archived_models(3), archived_models(4)
    rows = [models["logistic_platt"]["minus_global_elo"]
            for models in (previous, current)]
    if defect == "mismatch":
        rows[1]["bootstrap"]["seed"] = 31
    elif defect == "semantics_mismatch":
        rows[1]["brier_ci_probability_semantics"] = "OTHER"
    else:
        for row in rows:
            if defect == "empty":
                row["bootstrap"] = {}
            elif defect == "missing_seed":
                del row["bootstrap"]["seed"]
            elif defect == "missing_replicates":
                del row["bootstrap"]["replicates"]
            elif defect == "missing_semantics":
                del row["brier_ci_probability_semantics"]
            elif defect == "blank_semantics":
                row["brier_ci_probability_semantics"] = ""
            else:
                row["bootstrap"]["seed"] = True
    with pytest.raises(ValueError):
        compare(previous, current)


@pytest.mark.parametrize("defect", ["duplicate", "reverse_both", "reverse_current",
                                   "missing_fields", "bool_coverage", "bad_total",
                                   "baseline_mismatch", "bool_n", "bool_year",
                                   "missing_both_models"])
def test_repeat_comparison_rejects_invalid_matched_support(defect):
    previous, current = archived_models(3), archived_models(4)
    rows = [models["logistic_platt"] for models in (previous, current)]
    if defect == "reverse_current":
        rows[1]["folds"].reverse()
    elif defect == "missing_both_models":
        del previous["logistic_platt"]
        del current["logistic_platt"]
    elif defect == "bool_coverage":
        rows[1]["folds"][0]["coverage"] = True
    else:
        for row in rows:
            if defect == "duplicate":
                row["folds"][1]["year"] = row["folds"][0]["year"]
            elif defect == "reverse_both":
                row["folds"].reverse()
            elif defect == "missing_fields":
                for key in ("year", "n", "coverage"):
                    del row["folds"][0][key]
            elif defect == "bad_total":
                row["n"] += 1
            elif defect == "baseline_mismatch":
                row["n"] -= 1
                row["folds"][0]["n"] -= 1
            elif defect == "bool_n":
                row["folds"][0]["n"] = True
            else:
                row["folds"][0]["year"] = True
    with pytest.raises(ValueError):
        compare(previous, current)


@pytest.mark.parametrize("metric", ["log_loss_95ci", "brier_95ci"])
@pytest.mark.parametrize("bad", [None, [float("inf"), 1], [0, float("-inf")], [False, 1], [2, 1]])
def test_repeat_comparison_rejects_bad_interval_in_either_metric(metric, bad):
    previous, current = archived_models(3), archived_models(4)
    current["logistic_platt"]["minus_global_elo"][metric] = bad
    with pytest.raises(ValueError):
        compare(previous, current)


@pytest.mark.parametrize("defect", ["missing_baseline", "self_interval"])
def test_repeat_comparison_requires_baseline_without_self_interval(defect):
    previous, current = archived_models(3), archived_models(4)
    if defect == "missing_baseline":
        del previous["global_elo"]
    else:
        current["global_elo"]["minus_global_elo"] = {}
    with pytest.raises(ValueError):
        compare(previous, current)


def test_committed_repeat_comparison_evidence_matches_archived_sources():
    path = ROOT / "docs/research/p2_4_bootstrap_repeat_comparison_evidence_20261125.json"
    evidence = json.loads(path.read_text(encoding="utf-8"))
    expected_paths = {
        "docs/research/p2_3_fixed_ml_evidence_20261125.json",
        "docs/research/p2_4_fixed_ablation_evidence_20261125.json",
    }
    assert len(evidence["source_files"]) == 2
    assert {source["path"] for source in evidence["source_files"]} == expected_paths
    for source in evidence["source_files"]:
        # Hash canonical Git blobs, not Windows checkout line endings.
        data = subprocess.check_output(["git", "show", "HEAD:" + source["path"]], cwd=ROOT)
        assert hashlib.sha256(data).hexdigest() == source["sha256"]
        assert json.loads(data) == json.loads((ROOT / source["path"]).read_text(encoding="utf-8"))
    repeated = compare(archived_models(3), archived_models(4))
    assert evidence["repeated_p2_3_comparison"] == repeated
    intervals = [row["bootstrap_endpoint_differences"] for row in repeated.values()
                 if row["bootstrap_endpoint_differences"] is not None]
    endpoints = [x for row in intervals for pair in row.values() for x in pair]
    assert evidence["models_compared"] == len(repeated) == 9
    assert evidence["models_with_paired_intervals"] == len(intervals) == 8
    assert evidence["interval_endpoints_compared"] == len(endpoints) == 32
    assert evidence["max_abs_bootstrap_endpoint_difference"] == max(map(abs, endpoints))
    assert evidence["schema"] == "P2_4_BOOTSTRAP_REPEAT_COMPARISON_EVIDENCE_V1"
    assert evidence["difference_direction"] == "P2_4_MINUS_P2_3"
    for flag in ("new_model_fitting_performed", "future_holdout_accessed",
                 "official_match_draw_verified", "model_validation_trusted", "allocation_enabled"):
        assert evidence[flag] is False
    assert evidence["stake"] == 0
