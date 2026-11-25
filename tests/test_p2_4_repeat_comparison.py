"""Regression contract for P2.4 repeated bootstrap evidence."""
import json
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
