"""P1.4c tests: legacy tournament index metadata cannot authorize match ingestion."""
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

from atp_gate.legacy_archive_crosswalk import audit_legacy_archive_crosswalk


ROOT = Path(__file__).resolve().parents[1]
SHA = "a" * 64
ARCHIVE = "https://www.valuebetennis.com/tournaments/2024/02/archive.htm"


def original_inventory():
    group = {
        "year": 2024, "tournament_id": "12440",
        "names": ["Australian Open - Melbourne"],
        "categories": ["Grand Slam"], "surfaces": ["dur"],
        "round_counts": {"9": 1}, "candidate_matches": 1,
        "source_files": ["valuebetennis-matchs-2024.csv"],
        "first_observed_utc": "2024-01-23T10:00:00+00:00",
        "last_observed_utc": "2024-01-23T15:00:00+00:00",
        "metadata_conflict": False,
        "official_tier": None, "main_draw_verified": False,
    }
    return {
        "mode": "HISTORICAL_RESEARCH_ONLY",
        "counts": {"atp_candidate_matches": 1},
        "coverage": {"by_year": {"2024": 1}},
        "tier_mapping_verified": False, "main_draw_verified": False,
        "eligible_for_model_training": 0, "allocation_enabled": False, "stake": 0,
        "tournament_inventory": {
            "summary": {
                "candidate_matches": 1, "inventoried_matches": 1,
                "tournament_seasons": 1, "tournament_seasons_by_year": {"2024": 1},
            },
            "tournament_seasons": [group],
        },
    }


def official():
    return {
        "calendar_version": "P1_OFFICIAL_EVENT_CALENDAR_1",
        "inventory_sha256": SHA,
        "scope": "CURATED_OFFICIAL_EVENTS_ONLY",
        "events": [{
            "event_key": "ATP_2024_ROTTERDAM", "official_year": 2024,
            "official_event_name": "ABN AMRO Open", "official_tier": "ATP_500",
            "city": "Rotterdam", "start_date": "2024-02-12",
            "end_date": "2024-02-18",
            "results_archive_url": "https://www.atptour.com/en/scores/results-archive?year=2024",
            "tier_source_url": "https://www.atptour.com/en/news/rotterdam-2024-history-draw-schedule",
            "reviewed_on": "2026-11-23",
        }],
    }


def legacy():
    return {
        "manifest_version": "P1_LEGACY_INDEX_CROSSWALK_1",
        "inventory_sha256": SHA,
        "archive_url": ARCHIVE,
        "archive_record_type": "HISTORICAL_TOURNAMENT_INDEX_ONLY",
        "archive_page_rights": "UNVERIFIED_NOT_CSV_CC_BY_GRANT",
        "entries": [{
            "official_event_key": "ATP_2024_ROTTERDAM",
            "legacy_provider_tournament_id": "12495",
            "legacy_tournament_name": "ABN AMRO Open - Rotterdam",
            "legacy_start_date": "2024-02-12",
            "legacy_sex_marker": "H", "legacy_category": "Main tour",
            "evidence_url": ARCHIVE,
        }],
    }


def test_safe_crosswalk_reports_index_metadata_not_match_results():
    data, cal, manifest = original_inventory(), official(), legacy()
    before = [copy.deepcopy(x) for x in (data, cal, manifest)]
    result = audit_legacy_archive_crosswalk(data, cal, manifest, inventory_sha256=SHA)
    assert result["status"] == "LEGACY_CROSSWALK_REVIEW_REQUIRED"
    assert result["official_event_count"] == 1
    assert result["crosswalk_entries"] == 1
    assert result["archive_ids_absent_from_source"] == 1
    entry = result["entries"][0]
    assert entry["official_event_key"] == "ATP_2024_ROTTERDAM"
    assert entry["legacy_provider_tournament_id"] == "12495"
    assert entry["source_status"] == "NO_SOURCE_EVENT_CANDIDATE"
    assert entry["archive_record_type"] == "TOURNAMENT_INDEX_ONLY"
    assert entry["licensed_match_rows"] == 0
    assert entry["event_identity_verified"] is False
    assert result["legacy_archive_rights_verified"] is False
    assert result["legacy_match_results_available"] is False
    assert result["tier_mapping_verified"] is False
    assert result["main_draw_verified"] is False
    assert result["eligible_for_model_training"] == 0
    assert result["allocation_enabled"] is False
    assert result["stake"] == 0
    assert [data, cal, manifest] == before


@pytest.mark.parametrize("mutation", [
    "stale_hash", "extra_event", "missing_event",
    "wrong_id", "wrong_city", "wrong_date", "wta_gender",
    "wrong_category", "false_license", "bad_archive_url",
    "duplicate_id", "source_id_present", "wrong_provenance"
])
def test_bad_or_unauthorised_archive_claim_fails_closed(mutation):
    data, cal, manifest = original_inventory(), official(), legacy()
    entry = manifest["entries"][0]
    if mutation == "stale_hash":
        manifest["inventory_sha256"] = "0" * 64
    elif mutation == "extra_event":
        entry["official_event_key"] = "ATP_2024_DOHA"
    elif mutation == "missing_event":
        manifest["entries"] = []
    elif mutation == "wrong_id":
        entry["legacy_provider_tournament_id"] = "abc"
    elif mutation == "wrong_city":
        entry["legacy_tournament_name"] = "ABN AMRO Open - Dallas"
    elif mutation == "wrong_date":
        entry["legacy_start_date"] = "2024-10-12"
    elif mutation == "wta_gender":
        entry["legacy_sex_marker"] = "F"
    elif mutation == "wrong_category":
        entry["legacy_category"] = "ITF/Challengers (>$10K)"
    elif mutation == "false_license":
        manifest["archive_page_rights"] = "CC BY 4.0"
    elif mutation == "bad_archive_url":
        manifest["archive_url"] = "https://www.valuebetennis.com.evil.org/2024"
    elif mutation == "duplicate_id":
        manifest["entries"].append(copy.deepcopy(entry))
    elif mutation == "source_id_present":
        data["tournament_inventory"]["tournament_seasons"][0]["tournament_id"] = "12495"
    elif mutation == "wrong_provenance":
        manifest["archive_record_type"] = "DOWNLOADED_MATCH_DATA"
    with pytest.raises(ValueError):
        audit_legacy_archive_crosswalk(data, cal, manifest, inventory_sha256=SHA)


def test_curated_manifest_has_exact_twelve_atp_event_ids():
    ref = json.loads(
        (ROOT / "docs/registries/valuebetennis_legacy_2024_02_crosswalk_v1.json")
        .read_text(encoding="utf-8")
    )
    assert ref["manifest_version"] == "P1_LEGACY_INDEX_CROSSWALK_1"
    assert ref["inventory_sha256"] == (
        "eccb403bb6c0874e30f4e304c7be23678d2d1e6db095fd9174ee1753a225665b"
    )
    assert ref["archive_page_rights"] == "UNVERIFIED_NOT_CSV_CC_BY_GRANT"
    expected_ids = {
        "ATP_2024_CORDOBA": "12492",
        "ATP_2024_DALLAS": "12493",
        "ATP_2024_MARSEILLE": "12494",
        "ATP_2024_ROTTERDAM": "12495",
        "ATP_2024_BUENOS_AIRES": "12496",
        "ATP_2024_DELRAY_BEACH": "12497",
        "ATP_2024_DOHA": "12542",
        "ATP_2024_RIO_DE_JANEIRO": "12543",
        "ATP_2024_LOS_CABOS": "12544",
        "ATP_2024_DUBAI": "12570",
        "ATP_2024_ACAPULCO": "12571",
        "ATP_2024_SANTIAGO": "12572",
    }
    assert {x["official_event_key"]: x["legacy_provider_tournament_id"]
            for x in ref["entries"]} == expected_ids
    assert all(x["legacy_sex_marker"] == "H" for x in ref["entries"])


def test_cli_success_and_reject_input_overwrite(tmp_path):
    data, cal, manifest = original_inventory(), official(), legacy()
    data_path = tmp_path / "inventory.json"
    data_path.write_text(json.dumps(data), encoding="utf-8")
    sha = hashlib.sha256(data_path.read_bytes()).hexdigest()
    cal["inventory_sha256"] = manifest["inventory_sha256"] = sha
    cal_path = tmp_path / "calendar.json"
    manifest_path = tmp_path / "legacy.json"
    cal_path.write_text(json.dumps(cal), encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    output = tmp_path / "crosswalk.json"
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    cmd = [sys.executable, "-m", "atp_gate", "valuebetennis-legacy-crosswalk",
           str(data_path), str(cal_path), str(manifest_path)]
    ok = subprocess.run([*cmd, "--out", str(output)], env=env,
                        cwd=ROOT, capture_output=True, text=True)
    assert ok.returncode == 0, ok.stderr + ok.stdout
    summary = json.loads(ok.stdout)
    assert summary["status"] == "LEGACY_CROSSWALK_REVIEW_REQUIRED"
    assert summary["archive_ids_absent_from_source"] == 1
    assert summary["eligible_for_model_training"] == 0
    assert json.loads(output.read_text())["legacy_archive_rights_verified"] is False
    original = data_path.read_bytes()
    bad = subprocess.run([*cmd, "--out", str(data_path)], env=env,
                         cwd=ROOT, capture_output=True, text=True)
    assert bad.returncode == 2
    assert json.loads(bad.stdout)["status"] == "ERROR"
    assert data_path.read_bytes() == original
    manifest["inventory_sha256"] = "f" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    output.unlink()
    stale = subprocess.run([*cmd, "--out", str(output)], env=env,
                           cwd=ROOT, capture_output=True, text=True)
    assert stale.returncode == 2
    assert not output.exists()
