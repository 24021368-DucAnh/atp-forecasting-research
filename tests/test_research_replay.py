"""Reproducible-report contract: verify data, environment and actual holdout counts."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from atp_gate.research_replay import replay_saved_report
from atp_gate.research_train import run_research


ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC = ROOT / "examples" / "research_synthetic.csv"


def _make_report(tmp_path: Path):
    source = tmp_path / "fixture.csv"
    shutil.copyfile(SYNTHETIC, source)
    report = run_research([source], minimum_total=90, minimum_target=20, seed=13)
    report_path = tmp_path / "original_report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    return source, report, report_path


def test_report_records_actual_holdout_tier_counts_and_sample_total(tmp_path):
    _, report, _ = _make_report(tmp_path)
    holdout = report["holdout_target"]
    assert sum(holdout["tier_counts"].values()) == holdout["n"]
    assert set(holdout["tiers"]) == set(holdout["tier_counts"])
    assert holdout["tiers"] == ["ATP_500"]
    assert "GRAND_SLAM" in holdout["configured_target_tiers"]


def test_report_records_complete_replay_parameters_and_dependency_versions(tmp_path):
    _, report, _ = _make_report(tmp_path)
    cfg = report["training_configuration"]
    env = report["execution_environment"]
    assert cfg["minimum_total"] == 90
    assert cfg["minimum_target"] == 20
    assert cfg["random_state"] == 13
    assert env["python"]
    for library in ("numpy", "pandas", "scikit-learn", "xgboost"):
        assert env["packages"][library]
    assert report["allocation_enabled"] is False


def test_replay_of_unchanged_sources_reproduces_report(tmp_path):
    source, _, saved = _make_report(tmp_path)
    result = replay_saved_report(saved, [source])
    assert result["status"] == "REPRODUCED"
    assert result["reasons"] == []
    assert result["matching_sources"] == 1
    assert result["allocation_enabled"] is False
    assert result["validation_report_trusted"] is False
    assert result["stake"] == 0


def test_replay_detects_manually_tampered_metric(tmp_path):
    source, report, saved = _make_report(tmp_path)
    report["holdout_target"]["xgb_log_loss"] += 0.02
    saved.write_text(json.dumps(report), encoding="utf-8")
    result = replay_saved_report(saved, [source])
    assert result["status"] == "REJECT"
    assert "METRICS_OR_CONFIG_MISMATCH" in result["reasons"]


def test_replay_rejects_modified_source_even_before_fitting(tmp_path):
    source, _, saved = _make_report(tmp_path)
    with source.open("ab") as f:
        f.write(b"\n")
    result = replay_saved_report(saved, [source])
    assert result["status"] == "REJECT"
    assert "SOURCE_CONTENT_MISMATCH" in result["reasons"]


def test_replay_rejects_different_environment(tmp_path):
    source, report, saved = _make_report(tmp_path)
    report["execution_environment"]["packages"]["xgboost"] = "0.0.0"
    saved.write_text(json.dumps(report), encoding="utf-8")
    result = replay_saved_report(saved, [source])
    assert result["status"] == "REJECT"
    assert "ENVIRONMENT_MISMATCH" in result["reasons"]


def test_replay_rejects_legacy_report_without_versions(tmp_path):
    source, report, saved = _make_report(tmp_path)
    report.pop("execution_environment")
    saved.write_text(json.dumps(report), encoding="utf-8")
    result = replay_saved_report(saved, [source])
    assert result["status"] == "REJECT"
    assert "ENVIRONMENT_NOT_RECORDED" in result["reasons"]


def test_replay_rejects_untrusted_report_with_changed_safety_flags(tmp_path):
    source, report, saved = _make_report(tmp_path)
    report["allocation_enabled"] = True
    saved.write_text(json.dumps(report), encoding="utf-8")
    result = replay_saved_report(saved, [source])
    assert result["status"] == "REJECT"
    assert "UNSAFE_REPORT" in result["reasons"]


def test_windows_friendly_replay_cli_returns_nonzero_on_tampering(tmp_path):
    import os
    import subprocess
    import sys

    source, report, saved = _make_report(tmp_path)
    command = [sys.executable, str(ROOT / "scripts" / "replay_research.py"),
               str(saved), str(source)]
    ok = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    assert ok.returncode == 0, ok.stderr + ok.stdout
    assert json.loads(ok.stdout)["status"] == "REPRODUCED"

    report["holdout_target"]["elo_brier"] += 0.015
    saved.write_text(json.dumps(report), encoding="utf-8")
    bad = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    assert bad.returncode != 0
    assert json.loads(bad.stdout)["status"] == "REJECT"
