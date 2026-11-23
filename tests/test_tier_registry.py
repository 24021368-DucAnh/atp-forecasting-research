"""P1.3c red-green: explicit official tier claims, never automatic training authorization."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from atp_gate.tier_registry import audit_tier_registry

ROOT = Path(__file__).resolve().parents[1]
HASH = "a" * 64


def _event(year, tid, name, category, n=4):
    return {
        "year": year, "tournament_id": tid, "names": [name],
        "categories": [category], "surfaces": ["dur"],
        "round_counts": {"4": n}, "candidate_matches": n,
        "source_files": [f"vbt-{year}.csv"],
        "first_observed_utc": f"{year}-03-01T10:00:00+00:00",
        "last_observed_utc": f"{year}-03-02T10:00:00+00:00",
        "metadata_conflict": False, "official_tier": None,
        "main_draw_verified": False,
    }


def inventory(groups=None):
    if groups is None:
        groups = [
            _event(2024, "400", "Qatar ExxonMobil Open - Doha", "Main tour"),
            _event(2025, "500", "Qatar ExxonMobil Open - Doha", "Main tour"),
            _event(2024, "401", "Australian Open - Melbourne", "Grand Slam", 3),
            _event(2025, "501", "Unknown Open - City", "Main tour", 2),
        ]
    by_year = {}
    per_year = {}
    for group in groups:
        key = str(group["year"])
        by_year[key] = by_year.get(key, 0) + group["candidate_matches"]
        per_year[key] = per_year.get(key, 0) + 1
    total = sum(e["candidate_matches"] for e in groups)
    return {
        "mode": "HISTORICAL_RESEARCH_ONLY",
        "counts": {"atp_candidate_matches": total},
        "coverage": {"by_year": by_year},
        "tier_mapping_verified": False, "main_draw_verified": False,
        "allocation_enabled": False, "eligible_for_model_training": 0, "stake": 0,
        "tournament_inventory": {
            "summary": {
                "candidate_matches": total, "inventoried_matches": total,
                "tournament_seasons": len(groups),
                "tournament_seasons_by_year": per_year,
            },
            "tournament_seasons": groups,
        },
    }


def _entry(year, tid, name, tier, *, quality="UNVERIFIED",
           url="https://www.atptour.com/en/news/atp-500-upgrades-from-2025"):
    return {
        "utc_year": year, "tournament_id": tid,
        "observed_name": name, "official_edition_year": year,
        "official_tier": tier, "dataset_coverage": quality,
        "evidence_url": url, "evidence_note": "Primary-source ATP result",
        "reviewed_on": "2026-11-23",
    }


def registry():
    return {
        "registry_version": "P1_EDITION_TIER_REGISTRY_1",
        "inventory_sha256": HASH,
        "entries": [
            _entry(2024, "400", "Qatar ExxonMobil Open - Doha", "ATP_250"),
            _entry(2025, "500", "Qatar ExxonMobil Open - Doha", "ATP_500"),
            _entry(2024, "401", "Australian Open - Melbourne", "GRAND_SLAM",
                   quality="KNOWN_INCOMPLETE",
                   url="https://ausopen.com/articles/news/sinner-winner-italian-takes-first-major-ao-2024"),
        ],
        "expected_absent_events": [{
            "official_edition_year": 2024,
            "official_event_name": "ABN AMRO Open - Rotterdam",
            "official_tier": "ATP_500",
            "match_markers": ["Rotterdam"],
            "evidence_url": "https://www.atptour.com/en/news/rotterdam-2024-history-draw-schedule",
            "reviewed_on": "2026-11-23",
        }],
    }


def test_year_specific_tier_claims_not_promoted_into_training():
    data = inventory()
    reg = registry()
    before_data, before_reg = copy.deepcopy(data), copy.deepcopy(reg)
    got = audit_tier_registry(data, reg, inventory_sha256=HASH)
    assert got["status"] == "REVIEW_REQUIRED"
    assert got["reviewed_event_groups"] == 3
    assert got["unreviewed_event_groups"] == 1
    assert got["reviewed_tiers"]["ATP_250"]["event_groups"] == 1
    assert got["reviewed_tiers"]["ATP_500"]["event_groups"] == 1
    assert got["reviewed_tiers"]["GRAND_SLAM"]["event_groups"] == 1
    assert got["history_only_matches"] == 4
    assert got["potential_target_tier_matches"] == 7
    assert got["known_incomplete_target_matches"] == 3
    assert got["expected_absent_event_count"] == 1
    assert got["eligible_for_model_training"] == 0
    assert got["tier_mapping_verified"] is False
    assert got["main_draw_verified"] is False
    assert got["t60_quote_verified"] is False
    assert got["allocation_enabled"] is False and got["stake"] == 0
    assert data == before_data and reg == before_reg


@pytest.mark.parametrize("mutation", [
    "wrong_hash", "unknown_id", "wrong_name", "duplicate_claim",
    "bad_tier", "pretend_complete", "bad_url", "missing_evidence_note",
    "wrong_source_year", "bad_review_date", "bad_absent_alias",
])
def test_invalid_or_unverifiable_claims_fail_closed(mutation):
    data, reg = inventory(), registry()
    first = reg["entries"][0]
    if mutation == "wrong_hash":
        reg["inventory_sha256"] = "0" * 64
    elif mutation == "unknown_id":
        first["tournament_id"] = "9999"
    elif mutation == "wrong_name":
        first["observed_name"] = "another tournament"
    elif mutation == "duplicate_claim":
        reg["entries"].append(copy.deepcopy(first))
    elif mutation == "bad_tier":
        first["official_tier"] = "ATP_5000"
    elif mutation == "pretend_complete":
        first["dataset_coverage"] = "COMPLETE"
    elif mutation == "bad_url":
        first["evidence_url"] = "https://www.atptour.com.evil.net/en/news/blah"
    elif mutation == "missing_evidence_note":
        first["evidence_note"] = ""
    elif mutation == "wrong_source_year":
        first["official_edition_year"] = 2023
    elif mutation == "bad_review_date":
        first["reviewed_on"] = "not-date"
    elif mutation == "bad_absent_alias":
        data["tournament_inventory"]["tournament_seasons"].append(
            _event(2024, "402", "Rotterdam Championship - Rotterdam", "Main tour")
        )
        # Keep parent inventory internally consistent so alias check, not count mismatch, fails.
        data["counts"]["atp_candidate_matches"] += 4
        data["coverage"]["by_year"]["2024"] += 4
        sm = data["tournament_inventory"]["summary"]
        sm["candidate_matches"] += 4
        sm["inventoried_matches"] += 4
        sm["tournament_seasons"] += 1
        sm["tournament_seasons_by_year"]["2024"] += 1
    with pytest.raises(ValueError):
        audit_tier_registry(data, reg, inventory_sha256=HASH)


def test_cross_year_provider_id_cannot_be_reclassified_by_calendar_year():
    groups = [_event(2024, "44", "United Cup - Australia", "Main tour"),
              _event(2025, "44", "United Cup - Australia", "Main tour")]
    data = inventory(groups)
    reg = registry()
    reg["entries"] = [_entry(2024, "44", "United Cup - Australia", "ATP_250")]
    reg["expected_absent_events"] = []
    with pytest.raises(ValueError, match="cross"):
        audit_tier_registry(data, reg, inventory_sha256=HASH)


def test_no_tier_claims_still_yields_unreviewed_not_approval():
    reg = registry()
    reg["entries"] = []
    reg["expected_absent_events"] = []
    out = audit_tier_registry(inventory(), reg, inventory_sha256=HASH)
    assert out["reviewed_event_groups"] == 0
    assert out["unreviewed_event_groups"] == 4
    assert out["eligible_for_model_training"] == 0


def test_cli_summary_and_no_input_overwrite(tmp_path):
    original = tmp_path / "inventory.json"
    original.write_text(json.dumps(inventory()), encoding="utf-8")
    digest = hashlib.sha256(original.read_bytes()).hexdigest()
    reg = registry()
    reg["inventory_sha256"] = digest
    registry_file = tmp_path / "registry.json"
    registry_file.write_text(json.dumps(reg), encoding="utf-8")
    out_path = tmp_path / "audit.json"
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    cmd = [sys.executable, "-m", "atp_gate", "valuebetennis-tier-audit",
           str(original), str(registry_file)]
    ok = subprocess.run([*cmd, "--out", str(out_path)], env=env,
                        cwd=ROOT, capture_output=True, text=True)
    assert ok.returncode == 0, ok.stderr + ok.stdout
    summary = json.loads(ok.stdout)
    assert summary["status"] == "REVIEW_REQUIRED"
    assert summary["reviewed_event_groups"] == 3
    assert summary["eligible_for_model_training"] == 0
    assert json.loads(out_path.read_text())["expected_absent_event_count"] == 1
    before = original.read_bytes()
    bad = subprocess.run([*cmd, "--out", str(original)], env=env, cwd=ROOT,
                         capture_output=True, text=True)
    assert bad.returncode == 2
    assert json.loads(bad.stdout)["status"] == "ERROR"
    assert original.read_bytes() == before
    reg["inventory_sha256"] = "f" * 64
    registry_file.write_text(json.dumps(reg), encoding="utf-8")
    out_path.unlink()
    stale = subprocess.run([*cmd, "--out", str(out_path)], env=env, cwd=ROOT,
                           capture_output=True, text=True)
    assert stale.returncode == 2
    assert not out_path.exists()


def test_curated_snapshot_seed_is_explicit_and_never_claims_data_completeness():
    seed_path = ROOT / "docs" / "registries" / "valuebetennis_2022_2026_tiers_v1.json"
    seed = json.loads(seed_path.read_text(encoding="utf-8"))
    assert seed["registry_version"] == "P1_EDITION_TIER_REGISTRY_1"
    assert seed["inventory_sha256"] == (
        "eccb403bb6c0874e30f4e304c7be23678d2d1e6db095fd9174ee1753a225665b"
    )
    assert len(seed["entries"]) == 11
    assert {(r["utc_year"],r["tournament_id"]) for r in seed["entries"]} >= {
        (2024, "12440"), (2024, "12589"),
        (2024, "12777"), (2025, "14114"),
        (2025, "14168"), (2025, "14416")
    }
    assert all(
        entry["dataset_coverage"] in {"UNVERIFIED", "KNOWN_INCOMPLETE"}
        for entry in seed["entries"]
    )
    assert all(entry["official_tier"] in {
        "ATP_250", "ATP_500", "MASTERS_1000", "GRAND_SLAM", "OTHER"
    } for entry in seed["entries"])
    assert seed["expected_absent_events"][0]["match_markers"] == ["Rotterdam"]
