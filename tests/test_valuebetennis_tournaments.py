"""TDD: provider tournament-season grouping is an inventory, never tier approval."""
from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from pathlib import Path

from atp_gate.valuebetennis_source import inspect_valuebetennis_sources

ROOT = Path(__file__).resolve().parents[1]
COLUMNS = (
    "match_id", "date", "tournoi", "tournoi_id", "categorie", "genre",
    "surface", "tour", "joueur1", "joueur1_id", "joueur2", "joueur2_id",
    "cote1_ouverture", "cote2_ouverture", "cote1_cloture", "cote2_cloture",
    "vainqueur_id",
)


def sample(**changes):
    record = {
        "match_id": "101", "date": "2024-02-01 11:30:00",
        "tournoi": "Alpha Open", "tournoi_id": "99",
        "categorie": "Main tour", "genre": "atp", "surface": "dur",
        "tour": "4", "joueur1": "A One", "joueur1_id": "1",
        "joueur2": "B Two", "joueur2_id": "2", "vainqueur_id": "1",
        "cote1_ouverture": "1.84", "cote2_ouverture": "1.97",
        "cote1_cloture": "1.80", "cote2_cloture": "2.02",
    }
    record.update(changes)
    return record


def write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=COLUMNS, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)
    return path


def files(tmp_path):
    older = write(tmp_path / "provider-2024.csv", [
        sample(),
        sample(match_id="102", date="2024-02-02 11:30:00", tour="5",
               joueur1_id="3", joueur1="C Three", vainqueur_id="3"),
        sample(match_id="103", genre="wta"),
        sample(match_id="104", categorie="Challenger"),
    ])
    newer = write(tmp_path / "provider-2025.csv", [
        sample(match_id="105", date="2025-02-01 11:30:00", tour="6",
               tournoi="Alpha 2025", joueur1_id="4", joueur1="D Four",
               vainqueur_id="4"),
        sample(match_id="101", date="2024-02-01 11:30:00"),
    ])
    return older, newer


def test_inventory_has_separate_years_raw_round_counts_and_consistent_totals(tmp_path):
    a, b = files(tmp_path)
    report = inspect_valuebetennis_sources(
        [a, b], expected_start_year=2024, expected_end_year=2025,
        include_tournaments=True,
    )
    group = report["tournament_inventory"]
    assert report["counts"]["atp_candidate_matches"] == 3
    assert report["counts"]["duplicate_match_id"] == 1
    assert group["summary"]["candidate_matches"] == 3
    assert group["summary"]["inventoried_matches"] == 3
    assert group["summary"]["tournament_seasons"] == 2
    assert group["summary"]["missing_tournament_metadata"] == 0
    first, second = group["tournament_seasons"]
    assert (first["year"], first["tournament_id"]) == (2024, "99")
    assert (second["year"], second["tournament_id"]) == (2025, "99")
    assert first["round_counts"] == {"4": 1, "5": 1}
    assert second["round_counts"] == {"6": 1}
    assert first["candidate_matches"] == 2
    assert second["candidate_matches"] == 1
    assert first["source_files"] == ["provider-2024.csv"]
    assert group["status"] == "INVENTORIED_UNMAPPED"
    assert report["tier_mapping_verified"] is False
    assert report["main_draw_verified"] is False
    assert report["eligible_for_model_training"] == 0
    assert report["stake"] == 0


def test_conflicted_name_and_category_stay_unresolved(tmp_path):
    csv_path = write(tmp_path / "sample.csv", [
        sample(),
        sample(match_id="102", date="2024-02-02 11:30:00",
               tournoi="Different Event", categorie="Masters", tour="5"),
    ])
    report = inspect_valuebetennis_sources(csv_path, include_tournaments=True)
    entry = report["tournament_inventory"]["tournament_seasons"][0]
    assert entry["names"] == ["Alpha Open", "Different Event"]
    assert entry["categories"] == ["Main tour", "Masters"]
    assert entry["metadata_conflict"] is True
    assert report["tournament_inventory"]["summary"]["metadata_conflicts"] == 1
    assert report["tournament_inventory"]["status"] == "INCOMPLETE"


def test_bad_tournament_id_is_not_silently_inventoried(tmp_path):
    source = write(tmp_path / "bad.csv", [
        sample(),
        sample(match_id="102", date="2024-02-02 11:30:00", tournoi_id="??"),
        sample(match_id="103", date="2024-02-03 11:30:00", tournoi=""),
    ])
    result = inspect_valuebetennis_sources(source, include_tournaments=True)
    assert result["counts"]["atp_candidate_matches"] == 3
    inv = result["tournament_inventory"]
    assert inv["summary"]["inventoried_matches"] == 1
    assert inv["summary"]["missing_tournament_metadata"] == 2
    assert inv["status"] == "INCOMPLETE"
    assert "TOURNAMENT_METADATA_MISSING" in inv["warnings"]


def test_profile_default_contract_unchanged(tmp_path):
    path = write(tmp_path / "a.csv", [sample()])
    base = inspect_valuebetennis_sources(path)
    extended = inspect_valuebetennis_sources(path, include_tournaments=True)
    assert "tournament_inventory" not in base
    assert {key: val for key, val in extended.items() if key != "tournament_inventory"} == base


def test_cli_saves_full_audit_but_prints_compact_summary(tmp_path):
    a, b = files(tmp_path)
    output = tmp_path / "audit.json"
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    cmd = [sys.executable, "-m", "atp_gate", "valuebetennis-tournaments",
           "--out", str(output), "--start-year", "2024", "--end-year", "2025",
           str(a), str(b)]
    good = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
    assert good.returncode == 0, good.stdout + good.stderr
    summary = json.loads(good.stdout)
    stored = json.loads(output.read_text(encoding="utf-8"))
    assert summary["status"] == "INVENTORIED_UNMAPPED"
    assert summary["tournament_season_count"] == 2
    assert "tournament_seasons" not in summary  # summary should not be huge list
    assert stored["tournament_inventory"]["tournament_seasons"][0]["round_counts"]["4"] == 1
    assert stored["allocation_enabled"] is False
    assert stored["source_files"][0]["sha256"]


def test_cli_incomplete_years_have_nonzero_exit_with_evidence_saved(tmp_path):
    a, b = files(tmp_path)
    output = tmp_path / "incomplete.json"
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    cmd = [sys.executable, "-m", "atp_gate", "valuebetennis-tournaments",
           "--out", str(output), "--start-year", "2023", "--end-year", "2025",
           str(a), str(b)]
    response = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
    assert response.returncode == 2
    assert json.loads(response.stdout)["status"] == "INCOMPLETE"
    assert json.loads(output.read_text())["coverage"]["missing_expected_years"] == [2023]
