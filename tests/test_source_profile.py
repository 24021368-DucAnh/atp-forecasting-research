"""P1: accepted-only multi-season source quality and provenance profile."""
from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from atp_gate.source_profile import profile_historical_sources


HEADERS = (
    "ATP", "Tournament", "Date", "Series", "Surface", "Round", "Best of",
    "Winner", "Loser", "WRank", "LRank", "Comment", "B365W", "B365L",
)
ROOT = Path(__file__).resolve().parents[1]


def record(**updates):
    result = {
        "ATP": "9", "Tournament": "Monte Carlo", "Date": "15/04/2025",
        "Series": "Masters 1000", "Surface": "Clay", "Round": "1st Round",
        "Best of": "3", "Winner": "Player One", "Loser": "Player Two",
        "WRank": "10", "LRank": "20", "Comment": "Completed",
        "B365W": "1.70", "B365L": "2.20",
    }
    result.update(updates)
    return result


def write_file(path: Path, records) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(records)
    return path


def sample_files(tmp_path):
    older = write_file(tmp_path / "ATP_2025.csv", [
        record(),
        record(Date="16/04/2025", Tournament="Madrid", Series="ATP500",
               Winner="Player Three", Loser="Player Four", Surface="Hard"),
        record(Date="17/04/2025", Tournament="Retired Match", Comment="Retired"),
    ])
    recent = write_file(tmp_path / "ATP_2026.csv", [
        record(Date="17/04/2026", Tournament="Barcelona", Series="ATP500",
               Winner="Player Five", Loser="Player Six", Surface="Clay",
               B365W="", B365L="", WRank="", LRank="18"),
        record(Date="18/04/2026", Tournament="Doha", Series="ATP250",
               Winner="Player Seven", Loser="Player Eight", Surface="Hard"),
    ])
    return older, recent


def test_year_tier_surface_and_source_accepted_totals(tmp_path):
    older, recent = sample_files(tmp_path)
    report = profile_historical_sources([older, recent], expected_start_year=2025,
                                        expected_end_year=2026)
    assert report["status"] == "PROFILED"
    assert report["coverage"]["accepted_matches"] == 4
    assert report["source_audit"]["total_rows"] == 5
    assert report["source_audit"]["accepted"] == 4
    assert report["source_audit"]["not_completed"] == 1
    assert report["coverage"]["by_year"] == {"2025": 2, "2026": 2}
    assert report["coverage"]["by_tier"] == {"ATP_250": 1, "ATP_500": 2,
                                                "MASTERS_1000": 1}
    assert report["coverage"]["by_surface"] == {"Clay": 2, "Hard": 2}
    assert report["coverage"]["by_year_tier"]["2025"] == {"ATP_500": 1, "MASTERS_1000": 1}
    assert report["coverage"]["by_source"] == {"ATP_2025.csv": 2, "ATP_2026.csv": 2}
    assert report["coverage"]["observed_years"] == [2025, 2026]
    assert report["coverage"]["missing_expected_years"] == []
    assert report["coverage"]["first_match_date"] == "2025-04-15"
    assert report["coverage"]["last_match_date"] == "2026-04-18"
    assert report["source_audit"]["source_files"][0]["sha256"]
    assert report["source_identity_verified"] is False
    assert report["source_license_verified"] is False
    assert report["live_eligible"] is False
    assert report["allocation_enabled"] is False
    assert report["validation_report_trusted"] is False
    assert report["stake"] == 0


def test_missing_earlier_season_is_incomplete_not_success(tmp_path):
    older, recent = sample_files(tmp_path)
    report = profile_historical_sources([older, recent], expected_start_year=2024,
                                        expected_end_year=2026)
    assert report["status"] == "INCOMPLETE"
    assert report["coverage"]["missing_expected_years"] == [2024]
    assert "EXPECTED_YEAR_MISSING" in report["warnings"]


def test_per_year_missingness_is_accepted_row_only(tmp_path):
    older, recent = sample_files(tmp_path)
    report = profile_historical_sources([older, recent])
    assert report["quality"]["missing_odds"] == 1
    assert report["quality"]["missing_rank"] == 1
    assert report["quality"]["missing_odds_ratio"] == 0.25
    assert report["quality"]["missing_rank_ratio"] == 0.25
    assert report["quality"]["by_year"]["2025"]["missing_odds"] == 0
    assert report["quality"]["by_year"]["2026"]["missing_odds"] == 1
    assert report["quality"]["by_year"]["2026"]["missing_rank"] == 1
    assert report["coverage"]["unique_player_name_strings"] == 8


def test_duplicate_accepted_match_across_sources_only_counted_once(tmp_path):
    a = write_file(tmp_path / "one.csv", [record()])
    b = write_file(tmp_path / "two.csv", [record(), record(
        Date="20/04/2026", Tournament="Doha", Series="ATP250", Winner="A", Loser="B")])
    report = profile_historical_sources([a, b])
    assert report["source_audit"]["duplicate"] == 1
    assert report["coverage"]["accepted_matches"] == 2
    assert report["coverage"]["by_source"] == {"one.csv": 1, "two.csv": 1}
    assert "DUPLICATES_SKIPPED" in report["warnings"]


def test_same_basename_in_two_folders_is_rejected(tmp_path):
    a = write_file(tmp_path / "one" / "ATP.csv", [record()])
    b = write_file(tmp_path / "two" / "ATP.csv", [record(Date="20/04/2026")])
    with pytest.raises(ValueError, match="duplicate source basename"):
        profile_historical_sources([a, b])


def test_empty_accepted_sample_and_invalid_year_window_fail_closed(tmp_path):
    retired = write_file(tmp_path / "empty.csv", [record(Comment="Retired")])
    profile = profile_historical_sources([retired])
    assert profile["status"] == "INCOMPLETE"
    assert profile["coverage"]["accepted_matches"] == 0
    with pytest.raises(ValueError, match="expected.*year"):
        profile_historical_sources([retired], expected_start_year=2026)
    with pytest.raises(ValueError, match="expected.*year"):
        profile_historical_sources([retired], expected_start_year=2026, expected_end_year=2025)


def test_cli_profiles_without_training_and_rejects_missing_year(tmp_path):
    older, recent = sample_files(tmp_path)
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    base = [sys.executable, "-m", "atp_gate", "research-profile"]
    ok = subprocess.run([*base, "--start-year", "2025", "--end-year", "2026",
                         str(older), str(recent)], cwd=ROOT, capture_output=True, text=True, env=env)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert json.loads(ok.stdout)["status"] == "PROFILED"
    bad = subprocess.run([*base, "--start-year", "2024", "--end-year", "2026",
                          str(older), str(recent)], cwd=ROOT, capture_output=True, text=True, env=env)
    assert bad.returncode == 2
    assert json.loads(bad.stdout)["status"] == "INCOMPLETE"
