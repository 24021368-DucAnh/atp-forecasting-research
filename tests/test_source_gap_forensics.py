"""P1.4b TDD: raw CSV provenance and month/event gap investigation."""
from __future__ import annotations

import copy
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from atp_gate.source_gap_forensics import audit_source_gap

ROOT = Path(__file__).resolve().parents[1]
COLS = [
    "match_id", "date", "tournoi", "tournoi_id", "categorie", "genre",
    "surface", "tour", "joueur1", "joueur1_id", "joueur2", "joueur2_id",
    "vainqueur_id", "cote1_ouverture", "cote2_ouverture",
    "cote1_cloture", "cote2_cloture",
]


def row(**kw):
    data = dict(
        match_id="1", date="2024-01-10 12:00:00",
        tournoi="Another Open - Another City", tournoi_id="301",
        categorie="Main tour", genre="atp", surface="dur", tour="4",
        joueur1="A One", joueur1_id="1", joueur2="B Two", joueur2_id="2",
        vainqueur_id="1", cote1_ouverture="1.84", cote2_ouverture="2.04",
        cote1_cloture="1.85", cote2_cloture="2.02",
    )
    data.update(kw)
    return data


def write_csv(path, records):
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        w = csv.DictWriter(stream, fieldnames=COLS, delimiter=";")
        w.writeheader()
        w.writerows(records)
    return path


def sources(tmp_path, feb_accepted=False, duplicate=False):
    records = [
        row(),
        row(match_id="2", date="2024-02-14 10:00:00",
            tournoi="ABN AMRO Open - Rotterdam", tournoi_id="302",
            genre="wta", joueur1_id="11", joueur2_id="12", vainqueur_id="11"),
        row(match_id="3", date="2024-02-14 11:00:00",
            tournoi="ABN AMRO Open - Rotterdam", tournoi_id="303",
            categorie="Challenger"),
        row(match_id="4", date="2024-02-14 12:00:00",
            tournoi="ABN AMRO Open - Rotterdam", tournoi_id="304",
            vainqueur_id="999"),
        row(match_id="5", date="2024-02-14 13:00:00",
            tournoi="Different Open - Dallas", tournoi_id="305"),
        row(match_id="6", date="not-a-date",
            tournoi="ABN AMRO Open - Rotterdam", tournoi_id="302"),
    ]
    if feb_accepted:
        records.append(row(match_id="7", date="2024-02-15 12:00:00",
                           tournoi="ABN AMRO Open - Rotterdam",
                           tournoi_id="306"))
    if duplicate:
        records.append(row(match_id="1", date="2024-02-16 12:00:00",
                           tournoi="Different Open - Dallas", tournoi_id="307"))
    path = write_csv(tmp_path / "valuebetennis-matchs-2024.csv", records)

    group_list = [
        {
            "year": 2024, "tournament_id": "301",
            "names": ["Another Open - Another City"],
            "categories": ["Main tour"], "surfaces": ["dur"],
            "round_counts": {"4": 1}, "candidate_matches": 1,
            "source_files": [path.name],
            "first_observed_utc": "2024-01-10T12:00:00+00:00",
            "last_observed_utc": "2024-01-10T12:00:00+00:00",
            "metadata_conflict": False, "official_tier": None,
            "main_draw_verified": False,
        },
        {
            "year": 2024, "tournament_id": "305",
            "names": ["Different Open - Dallas"],
            "categories": ["Main tour"], "surfaces": ["dur"],
            "round_counts": {"4": 1}, "candidate_matches": 1,
            "source_files": [path.name],
            "first_observed_utc": "2024-02-14T13:00:00+00:00",
            "last_observed_utc": "2024-02-14T13:00:00+00:00",
            "metadata_conflict": False, "official_tier": None,
            "main_draw_verified": False,
        },
    ]
    if feb_accepted:
        group_list.append({
            "year": 2024, "tournament_id": "306",
            "names": ["ABN AMRO Open - Rotterdam"],
            "categories": ["Main tour"], "surfaces": ["dur"],
            "round_counts": {"4": 1}, "candidate_matches": 1,
            "source_files": [path.name],
            "first_observed_utc": "2024-02-15T12:00:00+00:00",
            "last_observed_utc": "2024-02-15T12:00:00+00:00",
            "metadata_conflict": False, "official_tier": None,
            "main_draw_verified": False,
        })
    count = len(group_list)
    inventory = {
        "mode": "HISTORICAL_RESEARCH_ONLY",
        "counts": {"atp_candidate_matches": count},
        "coverage": {"by_year": {"2024": count}, "by_source": {path.name: count}},
        "source_files": [{
            "name": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "size_bytes": path.stat().st_size,
        }],
        "tier_mapping_verified": False, "main_draw_verified": False,
        "allocation_enabled": False, "eligible_for_model_training": 0, "stake": 0,
        "tournament_inventory": {
            "summary": {
                "candidate_matches": count, "inventoried_matches": count,
                "tournament_seasons": count,
                "tournament_seasons_by_year": {"2024": count},
            },
            "tournament_seasons": group_list,
        }
    }
    raw = json.dumps(inventory).encode("utf-8")
    source_sha = hashlib.sha256(raw).hexdigest()
    calendar = {
        "calendar_version": "P1_OFFICIAL_EVENT_CALENDAR_1",
        "inventory_sha256": source_sha,
        "scope": "CURATED_OFFICIAL_EVENTS_ONLY",
        "events": [{
            "event_key": "ATP_2024_ROTTERDAM",
            "official_year": 2024, "official_event_name": "ABN AMRO Open",
            "official_tier": "ATP_500", "city": "Rotterdam",
            "start_date": "2024-02-12", "end_date": "2024-02-18",
            "results_archive_url": "https://www.atptour.com/en/scores/results-archive?year=2024",
            "tier_source_url": "https://www.atptour.com/en/news/rotterdam-2024-history-draw-schedule",
            "reviewed_on": "2026-11-23",
        }]
    }
    return path, inventory, calendar, source_sha


def test_raw_wta_challenger_and_invalid_winner_explain_filtered_source(tmp_path):
    path, inv, cal, digest = sources(tmp_path)
    before_inventory, before_calendar = copy.deepcopy(inv), copy.deepcopy(cal)
    result = audit_source_gap(path, inv, cal, inventory_sha256=digest, month="2024-02")
    assert result["status"] == "RAW_SOURCE_FORENSIC_REVIEW_REQUIRED"
    assert result["source_scope"] == "ONE_LOCAL_CSV_ONLY"
    assert result["source_total_rows"] == 6
    assert result["source_provisional_accepted"] == 2
    assert result["source_expected_accepted"] == 2
    assert result["month"]["raw_rows"] == 4
    assert result["month"]["by_genre"] == {"atp": 3, "wta": 1}
    assert result["month"]["atp_by_raw_category"] == {
        "Challenger": 1, "Main tour": 2
    }
    assert result["month"]["accepted_provisional"] == 1
    assert result["undated_rows_outside_month_attribution"] == 1
    rotterdam = result["official_event_diagnostics"][0]
    assert rotterdam["raw_city_date_rows"] == 3
    assert rotterdam["rejection_reasons"] == {
        "EXCLUDED_WTA": 1, "EXCLUDED_OTHER_CATEGORY": 1, "INVALID_WINNER": 1
    }
    assert rotterdam["status"] == "ONLY_FILTERED_RAW_CANDIDATES"
    assert result["eligible_for_model_training"] == 0
    assert result["allocation_enabled"] is False
    assert result["stake"] == 0
    assert inv == before_inventory and cal == before_calendar


def test_raw_city_match_no_candidate_is_not_a_global_absence_claim(tmp_path):
    path, inv, cal, digest = sources(tmp_path)
    cal["events"][0]["city"] = "Rio de Janeiro"
    result = audit_source_gap(path, inv, cal, inventory_sha256=digest, month="2024-02")
    assert result["official_event_diagnostics"][0]["status"] == "NO_MATCHING_RAW_CITY_DATE_ROWS"
    assert "CITY_NAME_MATCH_IS_NOT_EXHAUSTIVE" in result["warnings"]


def test_accepted_candidate_present_is_still_unverified_and_not_trainable(tmp_path):
    path, inv, cal, digest = sources(tmp_path, feb_accepted=True)
    out = audit_source_gap(path, inv, cal, inventory_sha256=digest, month="2024-02")
    assert out["source_provisional_accepted"] == 3
    diag = out["official_event_diagnostics"][0]
    assert diag["status"] == "ACCEPTED_SOURCE_CANDIDATE_PRESENT"
    assert diag["accepted_provisional_city_date_rows"] == 1
    assert out["main_draw_verified"] is False


def test_duplicate_id_does_not_inflate_accepted(tmp_path):
    path, inv, cal, digest = sources(tmp_path, duplicate=True)
    out = audit_source_gap(path, inv, cal, inventory_sha256=digest, month="2024-02")
    assert out["source_provisional_accepted"] == 2
    assert out["source_rejection_counts"]["DUPLICATE_MATCH_ID"] == 1


@pytest.mark.parametrize("tamper", ["csv_hash", "csv_size", "source_basename", "source_count",
                                    "inventory_sha", "bad_month", "bad_calendar"])
def test_stale_or_inconsistent_source_fails_closed(tmp_path, tamper):
    path, inv, cal, digest = sources(tmp_path)
    if tamper == "csv_hash":
        with path.open("ab") as stream:
            stream.write(b" ")
    elif tamper == "csv_size":
        inv["source_files"][0]["size_bytes"] += 1
    elif tamper == "source_basename":
        inv["source_files"][0]["name"] = "other.csv"
    elif tamper == "source_count":
        inv["coverage"]["by_source"][path.name] += 1
    elif tamper == "inventory_sha":
        cal["inventory_sha256"] = "0" * 64
    elif tamper == "bad_month":
        month = "2024-13"
    elif tamper == "bad_calendar":
        cal["events"][0]["official_year"] = 2025
    with pytest.raises(ValueError):
        audit_source_gap(path, inv, cal, inventory_sha256=digest,
                         month="2024-13" if tamper == "bad_month" else "2024-02")


def test_cli_success_and_fail_closed_no_overwrite(tmp_path):
    path, inv, cal, digest = sources(tmp_path)
    inventory_file = tmp_path / "inventory.json"
    inventory_file.write_text(json.dumps(inv), encoding="utf-8")
    digest = hashlib.sha256(inventory_file.read_bytes()).hexdigest()
    cal["inventory_sha256"] = digest
    official_file = tmp_path / "calendar.json"
    official_file.write_text(json.dumps(cal), encoding="utf-8")
    report_file = tmp_path / "gap.json"
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    cmd = [sys.executable, "-m", "atp_gate", "valuebetennis-gap-forensics",
           str(path), str(inventory_file), str(official_file), "--month", "2024-02"]
    ok = subprocess.run([*cmd, "--out", str(report_file)],
                        cwd=ROOT, capture_output=True, text=True, env=env)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    result = json.loads(ok.stdout)
    assert result["status"] == "RAW_SOURCE_FORENSIC_REVIEW_REQUIRED"
    assert result["official_event_count"] == 1
    assert json.loads(report_file.read_text())["month"]["raw_rows"] == 4
    bad = subprocess.run([*cmd, "--out", str(path)],
                         cwd=ROOT, capture_output=True, text=True, env=env)
    assert bad.returncode == 2
    assert json.loads(bad.stdout)["status"] == "ERROR"
    assert path.exists()
