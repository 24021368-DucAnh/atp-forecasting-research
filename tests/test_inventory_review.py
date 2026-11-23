"""Red-green tests: review saved provider tournament inventory without ML eligibility."""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from atp_gate.inventory_review import review_tournament_inventory

ROOT = Path(__file__).resolve().parents[1]


def event(year, tid, name, category, rounds, start):
    return {
        "year": year,
        "tournament_id": tid,
        "names": [name],
        "categories": [category],
        "surfaces": ["dur"],
        "round_counts": rounds,
        "candidate_matches": sum(rounds.values()),
        "source_files": [f"valuebetennis-matchs-{year}.csv"],
        "first_observed_utc": f"{start}T10:00:00+00:00",
        "last_observed_utc": f"{start}T20:00:00+00:00",
        "metadata_conflict": False,
        "official_tier": None,
        "main_draw_verified": False,
    }


def sample_report():
    groups = [
        event(2023, "44", "United Cup - Australia", "Main tour", {"8": 2}, "2023-12-29"),
        event(2024, "44", "United Cup - Australia", "Main tour", {"8": 3}, "2024-01-03"),
        event(2024, "45", "Australian Open - Melbourne", "Grand Slam", {"4": 4, "9": 2}, "2024-01-08"),
        event(2024, "46", "BNP Paribas Open - Indian Wells", "Masters", {"12": 1}, "2024-03-09"),
        event(2024, "47", "Nitto ATP Finals - Turin", "Masters", {"8": 2}, "2024-11-10"),
        event(2025, "48", "Wimbledon - London", "Grand Slam", {"12": 1}, "2025-07-01"),
    ]
    counts = {str(year): sum(e["candidate_matches"] for e in groups if e["year"] == year)
              for year in (2023, 2024, 2025)}
    group_counts = {str(year): sum(e["year"] == year for e in groups)
                    for year in (2023, 2024, 2025)}
    total = sum(counts.values())
    return {
        "mode": "HISTORICAL_RESEARCH_ONLY",
        "status": "INSPECTED_UNMAPPED",
        "counts": {"atp_candidate_matches": total},
        "coverage": {"by_year": counts},
        "source_files": [{"name":"sample.csv","sha256":"a"*64}],
        "tier_mapping_verified": False,
        "main_draw_verified": False,
        "eligible_for_model_training": 0,
        "allocation_enabled": False,
        "stake": 0,
        "tournament_inventory": {
            "status": "INVENTORIED_UNMAPPED",
            "summary": {
                "tournament_seasons": len(groups),
                "candidate_matches": total,
                "inventoried_matches": total,
                "missing_tournament_metadata": 0,
                "metadata_conflicts": 0,
                "tournament_seasons_by_year": group_counts,
            },
            "tournament_seasons": groups,
        },
    }


def test_flags_cross_calendar_year_ids_without_merging_or_model_approval():
    report = sample_report()
    before = copy.deepcopy(report)
    result = review_tournament_inventory(report)
    assert result["status"] == "REVIEW_REQUIRED"
    assert result["integrity"]["candidate_matches"] == 15
    assert result["integrity"]["tournament_season_groups"] == 6
    cross = result["cross_year_tournament_ids"]
    assert len(cross) == 1
    assert cross[0]["tournament_id"] == "44"
    assert cross[0]["years"] == [2023, 2024]
    assert cross[0]["candidate_matches"] == 5
    assert report == before
    assert result["tier_mapping_verified"] is False
    assert result["main_draw_verified"] is False
    assert result["eligible_for_model_training"] == 0
    assert result["allocation_enabled"] is False
    assert result["stake"] == 0


def test_flags_special_formats_not_as_regular_masters():
    out = review_tournament_inventory(sample_report())
    special = out["special_format_candidates"]
    assert special["group_count"] == 3
    assert special["candidate_matches"] == 7
    assert any(row["name"].startswith("Nitto ATP Finals") for row in special["events"])
    assert all(row["review_only"] is True for row in special["events"])


def test_flags_missing_final_for_grand_slam_but_not_special_atp_finals():
    out = review_tournament_inventory(sample_report())
    names = [row["name"] for row in out["missing_final_code_candidates"]]
    assert names == ["Australian Open - Melbourne"]
    assert out["missing_final_code_candidates"][0]["year"] == 2024
    assert out["missing_final_code_candidates"][0]["tournament_id"] == "45"


def test_flags_long_in_season_event_start_gap_not_offseason():
    out = review_tournament_inventory(sample_report())
    gaps = out["large_event_start_gaps"]
    assert len(gaps) == 1
    assert gaps[0]["year"] == 2024
    assert gaps[0]["days"] == 61
    assert gaps[0]["from_event"] == "Australian Open - Melbourne"
    assert gaps[0]["to_event"] == "BNP Paribas Open - Indian Wells"


@pytest.mark.parametrize("tamper", ["global_count", "round_count", "duplicate_key",
                                      "year_count", "invalid_id", "forged_tier"])
def test_reconciliation_or_trust_violation_fails_closed(tamper):
    report = sample_report()
    groups = report["tournament_inventory"]["tournament_seasons"]
    if tamper == "global_count":
        report["counts"]["atp_candidate_matches"] += 1
    elif tamper == "round_count":
        groups[0]["round_counts"]["8"] += 1
    elif tamper == "duplicate_key":
        groups[1]["tournament_id"] = "45"
    elif tamper == "year_count":
        report["coverage"]["by_year"]["2024"] += 1
    elif tamper == "invalid_id":
        groups[0]["tournament_id"] = "not-id"
    elif tamper == "forged_tier":
        report["tier_mapping_verified"] = True
    with pytest.raises(ValueError):
        review_tournament_inventory(report)


def test_cli_success_and_corrupt_source_error(tmp_path):
    report_file = tmp_path / "inventory.json"
    output = tmp_path / "review.json"
    report_file.write_text(json.dumps(sample_report()), encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    base = [sys.executable, "-m", "atp_gate", "valuebetennis-review", str(report_file)]
    valid = subprocess.run([*base, "--out", str(output)],
        cwd=ROOT, env=env, capture_output=True, text=True)
    assert valid.returncode == 0, valid.stdout + valid.stderr
    compact = json.loads(valid.stdout)
    assert compact["status"] == "REVIEW_REQUIRED"
    assert compact["cross_year_event_ids"] == 1
    assert compact["special_format_groups"] == 3
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert len(saved["cross_year_tournament_ids"]) == 1
    assert saved["eligible_for_model_training"] == 0

    corrupt = sample_report()
    corrupt["counts"]["atp_candidate_matches"] += 1
    report_file.write_text(json.dumps(corrupt), encoding="utf-8")
    output.unlink()
    failed = subprocess.run([*base, "--out", str(output)],
        cwd=ROOT, env=env, capture_output=True, text=True)
    assert failed.returncode == 2
    assert json.loads(failed.stdout)["status"] == "ERROR"
    assert not output.exists()


def test_cli_never_overwrites_the_original_inventory(tmp_path):
    original = tmp_path / "original.json"
    contents = json.dumps(sample_report())
    original.write_text(contents, encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    result = subprocess.run(
        [sys.executable, "-m", "atp_gate", "valuebetennis-review",
         str(original), "--out", str(original)],
        cwd=ROOT, env=env, capture_output=True, text=True,
    )
    assert result.returncode == 2
    assert json.loads(result.stdout)["status"] == "ERROR"
    assert original.read_text(encoding="utf-8") == contents


def test_cli_without_output_file_is_read_only(tmp_path):
    original = tmp_path / "original.json"
    original.write_text(json.dumps(sample_report()), encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    before = sorted(p.name for p in tmp_path.iterdir())
    result = subprocess.run(
        [sys.executable, "-m", "atp_gate", "valuebetennis-review",
         str(original)], cwd=ROOT, env=env, capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout)["status"] == "REVIEW_REQUIRED"
    assert sorted(p.name for p in tmp_path.iterdir()) == before
