"""TDD P1.4a: authoritative ATP event expectations vs provisional source inventory.

A city/date overlap is only a source candidate; no train/live approval.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from atp_gate.official_calendar_coverage import audit_official_calendar_coverage


ROOT = Path(__file__).resolve().parents[1]
SHA = "a" * 64


def source_group(year, tournament_id, name, start, end=None, n=3):
    end = end or start
    return {
        "year": year, "tournament_id": tournament_id,
        "names": [name], "categories": ["Main tour"],
        "surfaces": ["dur"], "round_counts": {"4": n},
        "candidate_matches": n, "source_files": [f"source-{year}.csv"],
        "first_observed_utc": start + "T10:00:00+00:00",
        "last_observed_utc": end + "T15:00:00+00:00",
        "metadata_conflict": False, "official_tier": None,
        "main_draw_verified": False,
    }


def inventory(groups=None):
    groups = groups if groups is not None else [
        source_group(2024, "100", "Australian Open - Melbourne",
                     "2024-01-08", "2024-01-23"),
    ]
    n = sum(g["candidate_matches"] for g in groups)
    by_year = {}
    count_year = {}
    for group in groups:
        y = str(group["year"])
        by_year[y] = by_year.get(y, 0) + group["candidate_matches"]
        count_year[y] = count_year.get(y, 0) + 1
    return {
        "mode": "HISTORICAL_RESEARCH_ONLY",
        "counts": {"atp_candidate_matches": n},
        "coverage": {"by_year": by_year},
        "tier_mapping_verified": False, "main_draw_verified": False,
        "allocation_enabled": False,
        "eligible_for_model_training": 0, "stake": 0,
        "tournament_inventory": {
            "summary": {
                "tournament_seasons": len(groups),
                "candidate_matches": n, "inventoried_matches": n,
                "tournament_seasons_by_year": count_year,
            },
            "tournament_seasons": groups,
        },
    }


def official_event(city="Rotterdam", date="2024-02-12", end="2024-02-18",
                   tier="ATP_500"):
    return {
        "event_key": f"ATP_2024_{city.upper().replace(' ', '_')}",
        "official_year": 2024,
        "official_event_name": "ABN AMRO Open" if city == "Rotterdam" else "ATP Tour event",
        "official_tier": tier,
        "city": city,
        "start_date": date, "end_date": end,
        "results_archive_url": "https://www.atptour.com/en/scores/results-archive?year=2024",
        "tier_source_url": "https://www.atptour.com/-/media/files/final-2024-atp-calendar.pdf",
        "reviewed_on": "2026-11-23",
    }


def calendar(events=None):
    return {
        "calendar_version": "P1_OFFICIAL_EVENT_CALENDAR_1",
        "inventory_sha256": SHA,
        "scope": "CURATED_OFFICIAL_EVENTS_ONLY",
        "events": events if events is not None else [official_event()],
    }


def test_no_february_source_yields_missing_event_without_creating_rows():
    original = inventory()
    cal = calendar()
    orig_before, cal_before = copy.deepcopy(original), copy.deepcopy(cal)
    out = audit_official_calendar_coverage(original, cal, inventory_sha256=SHA)
    assert out["status"] == "COVERAGE_REVIEW_REQUIRED"
    assert out["source_inventory_integrity"] == "RECONCILED"
    assert out["official_event_count"] == 1
    assert out["missing_official_events"] == 1
    assert out["candidate_official_events"] == 0
    assert out["ambiguous_official_events"] == 0
    assert out["missing_by_tier"]["ATP_500"] == 1
    assert out["events"][0]["status"] == "NO_SOURCE_EVENT_CANDIDATE"
    assert out["events"][0]["candidate_source_groups"] == []
    assert out["eligible_for_model_training"] == 0
    assert out["allocation_enabled"] is False and out["stake"] == 0
    assert original == orig_before and cal == cal_before


def test_date_and_city_suffix_match_remains_unverified_candidate():
    src = inventory([
        source_group(2024, "101", "ABN AMRO Open - Rotterdam",
                     "2024-02-10", "2024-02-18"),
    ])
    out = audit_official_calendar_coverage(src, calendar(), inventory_sha256=SHA)
    assert out["missing_official_events"] == 0
    assert out["candidate_official_events"] == 1
    event = out["events"][0]
    assert event["status"] == "SOURCE_CANDIDATE_UNVERIFIED"
    assert event["candidate_source_groups"][0]["tournament_id"] == "101"
    assert event["candidate_source_groups"][0]["candidate_matches"] == 3
    assert out["main_draw_verified"] is False
    assert out["tier_mapping_verified"] is False


def test_source_group_in_wrong_year_or_month_cannot_match():
    src = inventory([
        source_group(2024, "102", "ABN AMRO Open - Rotterdam", "2024-07-01"),
        source_group(2025, "103", "ABN AMRO Open - Rotterdam", "2025-02-12"),
    ])
    out = audit_official_calendar_coverage(src, calendar(), inventory_sha256=SHA)
    assert out["missing_official_events"] == 1
    assert out["events"][0]["candidate_source_groups"] == []


def test_two_same_city_date_source_groups_are_flagged_ambiguous_not_merged():
    src = inventory([
        source_group(2024, "104", "Other Open - Rotterdam", "2024-02-12"),
        source_group(2024, "105", "ABN AMRO Open - Rotterdam", "2024-02-13"),
    ])
    out = audit_official_calendar_coverage(src, calendar(), inventory_sha256=SHA)
    assert out["ambiguous_official_events"] == 1
    assert out["events"][0]["status"] == "AMBIGUOUS_SOURCE_CANDIDATES"
    assert len(out["events"][0]["candidate_source_groups"]) == 2
    assert out["eligible_for_model_training"] == 0


@pytest.mark.parametrize("tamper", [
    "hash", "duplicate_event", "wrong_evidence_host",
    "wrong_tier", "bad_date", "bad_year", "reversed_dates", "untrusted_inventory"
])
def test_bogus_calendars_and_untrusted_inventory_fail_closed(tamper):
    src, ref = inventory(), calendar()
    if tamper == "hash":
        ref["inventory_sha256"] = "0" * 64
    elif tamper == "duplicate_event":
        ref["events"].append(copy.deepcopy(ref["events"][0]))
    elif tamper == "wrong_evidence_host":
        ref["events"][0]["tier_source_url"] = "https://www.atptour.com.evil.com/calendar"
    elif tamper == "wrong_tier":
        ref["events"][0]["official_tier"] = "ATP_400"
    elif tamper == "bad_date":
        ref["events"][0]["start_date"] = "2024-02-40"
    elif tamper == "bad_year":
        ref["events"][0]["official_year"] = 2025
    elif tamper == "reversed_dates":
        ref["events"][0]["start_date"] = "2024-02-19"
    elif tamper == "untrusted_inventory":
        src["allocation_enabled"] = True
    with pytest.raises(ValueError):
        audit_official_calendar_coverage(src, ref, inventory_sha256=SHA)


def test_source_city_normalization_handles_accents_not_fuzzy_event_identity():
    event = official_event(city="Córdoba", date="2024-02-05", end="2024-02-11", tier="ATP_250")
    src = inventory([source_group(2024, "106", "Cordoba Open - Cordoba", "2024-02-04")])
    out = audit_official_calendar_coverage(src, calendar([event]), inventory_sha256=SHA)
    assert out["candidate_official_events"] == 1
    assert out["events"][0]["status"] == "SOURCE_CANDIDATE_UNVERIFIED"


def test_source_calendar_february_2024_has_twelve_events_and_correct_tiers():
    path = ROOT / "docs" / "registries" / "atp_2024_february_official_events_v1.json"
    ref = json.loads(path.read_text(encoding="utf-8"))
    assert ref["inventory_sha256"] == (
        "eccb403bb6c0874e30f4e304c7be23678d2d1e6db095fd9174ee1753a225665b"
    )
    assert len(ref["events"]) == 12
    assert sum(e["official_tier"] == "ATP_500" for e in ref["events"]) == 4
    assert sum(e["official_tier"] == "ATP_250" for e in ref["events"]) == 8
    assert all(e["start_date"].startswith("2024-02-") for e in ref["events"])
    assert len({e["event_key"] for e in ref["events"]}) == 12


def test_calendar_cli_json_and_stale_snapshot_rejection(tmp_path):
    raw = tmp_path / "inventory.json"
    raw.write_text(json.dumps(inventory()), encoding="utf-8")
    sha = hashlib.sha256(raw.read_bytes()).hexdigest()
    official = calendar()
    official["inventory_sha256"] = sha
    evidence = tmp_path / "calendar.json"
    evidence.write_text(json.dumps(official), encoding="utf-8")
    output = tmp_path / "audit.json"
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    base = [sys.executable, "-m", "atp_gate", "valuebetennis-calendar-audit",
            str(raw), str(evidence)]
    ok = subprocess.run([*base, "--out", str(output)], capture_output=True,
                        text=True, cwd=ROOT, env=env)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert json.loads(ok.stdout)["status"] == "COVERAGE_REVIEW_REQUIRED"
    assert json.loads(output.read_text())["missing_official_events"] == 1
    original = raw.read_bytes()
    bad = subprocess.run([*base, "--out", str(raw)], capture_output=True,
                         text=True, cwd=ROOT, env=env)
    assert bad.returncode == 2
    assert json.loads(bad.stdout)["status"] == "ERROR"
    assert raw.read_bytes() == original
    official["inventory_sha256"] = "f" * 64
    evidence.write_text(json.dumps(official), encoding="utf-8")
    output.unlink()
    stale = subprocess.run([*base, "--out", str(output)], capture_output=True,
                           text=True, cwd=ROOT, env=env)
    assert stale.returncode == 2
    assert not output.exists()
