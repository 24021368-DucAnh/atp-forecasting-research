"""Source-level Valuebetennis ATP identity/data-quality tests (no ML training)."""
from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
import sys

import pytest

from atp_gate.valuebetennis_source import inspect_valuebetennis_sources


COLUMNS = [
    "match_id", "date", "tournoi", "tournoi_id", "categorie", "genre",
    "surface", "tour", "joueur1", "joueur1_id", "joueur2", "joueur2_id",
    "cote1_ouverture", "cote2_ouverture", "cote1_cloture",
    "cote2_cloture", "vainqueur_id", "score", "duree_min",
]


def row(**changes):
    result = dict(
        match_id="1001", date="2024-04-04 10:00:00", tournoi="Event A",
        tournoi_id="99", categorie="Main tour", genre="atp", surface="Hard",
        tour="7", joueur1="Alexander Ace", joueur1_id="101",
        joueur2="Boris Beta", joueur2_id="102",
        cote1_ouverture="1.88", cote2_ouverture="1.96",
        cote1_cloture="1.80", cote2_cloture="2.01",
        vainqueur_id="101", score="6-4 6-4", duree_min="88",
    )
    result.update(changes)
    return result


def write_csv(path, records, columns=COLUMNS):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter=";")
        writer.writeheader()
        writer.writerows({name: record.get(name, '') for name in columns} for record in records)
    return path


def files(tmp_path):
    first = write_csv(tmp_path / "valuebetennis-2024.csv", [
        row(),
        row(match_id="2001", genre="wta", joueur1_id="501",
            joueur2_id="502", vainqueur_id="501"),
    ])
    second = write_csv(tmp_path / "valuebetennis-2025.csv", [
        row(match_id="3001", date="2025-03-03T12:20:00Z", tournoi_id="100",
            categorie="Masters", joueur1="Alex Ace", joueur2="Clive Charlie",
            joueur2_id="103", vainqueur_id="103"),
        row(match_id="4001", date="2025-04-01 08:00:00", categorie="Challenger"),
    ])
    return first, second


def test_documented_semicolon_schema_and_atp_only_candidates(tmp_path):
    first, second = files(tmp_path)
    report = inspect_valuebetennis_sources(
        [first, second], expected_start_year=2024, expected_end_year=2025
    )
    assert report["status"] == "INSPECTED_UNMAPPED"
    assert report["mode"] == "HISTORICAL_RESEARCH_ONLY"
    assert report["counts"]["total_rows"] == 4
    assert report["counts"]["atp_candidate_matches"] == 2
    assert report["counts"]["excluded_wta"] == 1
    assert report["counts"]["excluded_other_category"] == 1
    assert report["coverage"]["by_year"] == {"2024": 1, "2025": 1}
    assert report["coverage"]["by_category"] == {"Main tour": 1, "Masters": 1}
    assert report["coverage"]["unique_player_ids"] == 3
    assert report["identity_quality"]["ids_with_multiple_display_names"] == 1
    assert report["source_files"][0]["sha256"] == hashlib.sha256(first.read_bytes()).hexdigest()
    assert report["tier_mapping_verified"] is False
    assert report["main_draw_verified"] is False
    assert report["source_file_origin_verified"] is False
    assert report["t60_quote_verified"] is False
    assert report["eligible_for_model_training"] == 0
    assert report["allocation_enabled"] is False
    assert report["stake"] == 0


def test_bad_identity_winner_and_round_are_excluded(tmp_path):
    source = write_csv(tmp_path / "a.csv", [
        row(),
        row(match_id="2", joueur2_id="101"),
        row(match_id="3", vainqueur_id="999"),
        row(match_id="4", joueur1_id="not-id"),
        row(match_id="5", tour="14"),
        row(match_id="6", date="not-a-time"),
    ])
    report = inspect_valuebetennis_sources(source)
    assert report["counts"]["atp_candidate_matches"] == 1
    assert report["counts"]["invalid_identity"] == 2
    assert report["counts"]["invalid_winner"] == 1
    assert report["counts"]["invalid_round"] == 1
    assert report["counts"]["invalid_date"] == 1


def test_duplicate_match_id_across_files_is_not_double_counted(tmp_path):
    first, second = files(tmp_path)
    rows = [row(match_id="1001"), row(match_id="3002", date="2025-04-01 12:30:00")]
    write_csv(second, rows)
    report = inspect_valuebetennis_sources([first, second])
    assert report["counts"]["duplicate_match_id"] == 1
    assert report["counts"]["atp_candidate_matches"] == 2
    assert "DUPLICATE_MATCH_IDS_EXCLUDED" in report["warnings"]


def test_missing_price_fields_do_not_create_t60_quote(tmp_path):
    source = write_csv(tmp_path / "a.csv", [
        row(cote1_ouverture="", cote2_ouverture="", cote1_cloture="1.86", cote2_cloture=""),
        row(match_id="2", cote1_cloture="not-odds", cote2_cloture="2.04"),
    ])
    report = inspect_valuebetennis_sources(source)
    assert report["counts"]["atp_candidate_matches"] == 2
    assert report["price_quality"]["missing_opening_pair"] == 1
    assert report["price_quality"]["missing_closing_pair"] == 2
    assert report["t60_quote_verified"] is False


def test_missing_expected_year_and_no_atp_candidate_fail_closed(tmp_path):
    first, second = files(tmp_path)
    report = inspect_valuebetennis_sources(
        [first, second], expected_start_year=2022, expected_end_year=2025
    )
    assert report["status"] == "INCOMPLETE"
    assert report["coverage"]["missing_expected_years"] == [2022, 2023]
    assert "EXPECTED_SEASONS_MISSING" in report["warnings"]

    only_wta = write_csv(tmp_path / "wta.csv", [
        row(genre="wta", joueur1_id="301", joueur2_id="302", vainqueur_id="301")
    ])
    assert inspect_valuebetennis_sources(only_wta)["status"] == "INCOMPLETE"


def test_invalid_schema_year_range_and_duplicate_basename_are_rejected(tmp_path):
    invalid = write_csv(tmp_path / "bad.csv", [row()], columns=["match_id"])
    with pytest.raises(ValueError, match="missing columns"):
        inspect_valuebetennis_sources(invalid)
    first, second = files(tmp_path)
    with pytest.raises(ValueError, match="expected.*year"):
        inspect_valuebetennis_sources(first, expected_start_year=2024)
    with pytest.raises(ValueError, match="expected.*year"):
        inspect_valuebetennis_sources(first, expected_start_year=2025, expected_end_year=2024)
    same = write_csv(tmp_path / "subdir" / first.name, [row()])
    with pytest.raises(ValueError, match="duplicate source basename"):
        inspect_valuebetennis_sources([first, same])


def test_player_name_collision_not_accepted_as_canonical_mapping(tmp_path):
    source = write_csv(tmp_path / "a.csv", [
        row(),
        row(match_id="2", joueur1="Alexander Ace", joueur1_id="201",
            joueur2_id="103", joueur2="C. Other", vainqueur_id="103"),
    ])
    report = inspect_valuebetennis_sources(source)
    assert report["identity_quality"]["display_names_with_multiple_ids"] == 1
    assert report["identity_mapping_verified"] is False


def test_cli_returns_nonzero_if_requested_seasons_missing(tmp_path):
    first, second = files(tmp_path)
    env = {**os.environ, "PYTHONPATH": "src"}
    base = [sys.executable, "-m", "atp_gate", "valuebetennis-profile"]
    ok = subprocess.run(
        [*base, "--start-year", "2024", "--end-year", "2025",
         str(first), str(second)],
        capture_output=True, text=True, env=env,
    )
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert json.loads(ok.stdout)["status"] == "INSPECTED_UNMAPPED"
    bad = subprocess.run(
        [*base, "--start-year", "2022", "--end-year", "2025",
         str(first), str(second)],
        capture_output=True, text=True, env=env,
    )
    assert bad.returncode == 2
    assert json.loads(bad.stdout)["status"] == "INCOMPLETE"


def test_date_only_is_not_accepted_as_utc_match_timestamp(tmp_path):
    source = write_csv(tmp_path / "date_only.csv", [row(date="2025-05-01")])
    report = inspect_valuebetennis_sources(source)
    assert report["counts"]["atp_candidate_matches"] == 0
    assert report["counts"]["invalid_date"] == 1
    assert report["status"] == "INCOMPLETE"


def test_unknown_genre_is_not_mislabelled_as_wta(tmp_path):
    source = write_csv(tmp_path / "mixed_genre.csv", [
        row(genre="itf"),
        row(match_id="2", genre="wta", joueur1_id="901",
            joueur2_id="902", vainqueur_id="901"),
    ])
    report = inspect_valuebetennis_sources(source)
    assert report["counts"]["excluded_wta"] == 1
    assert report["counts"]["excluded_other_genre"] == 1
