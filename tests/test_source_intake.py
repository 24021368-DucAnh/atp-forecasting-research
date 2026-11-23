"""Fail-closed local P1.4d correction-source intake; synthetic bytes only."""
from datetime import datetime, timezone
from hashlib import sha256

import pytest

from atp_gate.source_intake import audit_source_intake

ASOF = datetime(2026, 11, 24, 0, 0, tzinfo=timezone.utc)
INVENTORY = "e" * 64
EVENTS = {"ATP_2024_DALLAS", "ATP_2024_ROTTERDAM"}


def manifest(path, *, inventory=INVENTORY):
    data = path.read_bytes()
    return {
        "version": "P1_AUTHORIZED_SOURCE_INTAKE_1",
        "inventory_sha256": inventory,
        "source": {
            "name": path.name,
            "sha256": sha256(data).hexdigest(),
            "size_bytes": len(data),
            "source_url": "https://example.org/download/2024-02.csv",
            "retrieved_at_utc": "2026-11-23T12:00:00Z",
            "format": "CSV",
            "row_count_claimed": 1,
        },
        "scope_event_keys": ["ATP_2024_DALLAS"],
        "permission": {
            "scope": "2024_FEB_MATCH_LEVEL_EXPORT",
            "evidence_url": "https://example.org/licence",
            "report_id": "permission-001",
            "report_sha256": "a" * 64,
            "ai_training_allowed": True,
            "commercial_use_allowed": True,
        },
        "draw_review": {
            "report_id": "draw-review-001",
            "report_sha256": "b" * 64,
            "verified_official_match_ids": True,
            "complete_main_draw": True,
        },
    }


@pytest.fixture
def source(tmp_path):
    f = tmp_path / "licensed-repair.csv"
    f.write_text("match_id,player_a\nsynthetic-1,synthetic-2\n", encoding="utf-8")
    return f


def check(source, m, *, trusted=None):
    return audit_source_intake(
        source, m, inventory_sha256=INVENTORY,
        allowed_event_keys=EVENTS, as_of=ASOF, trusted_permission_reports=trusted,
    )


def test_self_attested_permissions_never_authorize_training(source):
    result = check(source, manifest(source))
    assert result["status"] == "NO_AUTHORIZED_HISTORICAL_REPAIR_SOURCE"
    assert result["rights_reviewed"] is False
    assert result["eligible_for_model_training"] == 0
    assert result["allocation_enabled"] is False and result["stake"] == 0


def test_matching_independent_rights_receipt_does_not_certify_match_data(source):
    result = check(source, manifest(source), trusted={"permission-001": "a" * 64})
    assert result["status"] == "SOURCE_PERMISSION_REVIEWED_MATCH_AUDIT_PENDING"
    assert result["rights_reviewed"] is True
    assert result["main_draw_verified"] is False
    assert result["eligible_for_model_training"] == 0


def test_rights_hash_mismatch_remains_denied(source):
    result = check(source, manifest(source), trusted={"permission-001": "c" * 64})
    assert result["status"] == "NO_AUTHORIZED_HISTORICAL_REPAIR_SOURCE"


@pytest.mark.parametrize("field,bad", [
    ("inventory_sha256", "a" * 64),
    ("version", "fake"),
    ("scope_event_keys", ["ATP_2024_DALLAS", "ATP_2024_DALLAS"]),
    ("scope_event_keys", ["ATP_2024_UNKNOWN"]),
])
def test_bad_manifest_scope_rejected(source, field, bad):
    m = manifest(source)
    m[field] = bad
    with pytest.raises(ValueError):
        check(source, m)


def test_mismatched_sha_refuses_altered_source(source):
    m = manifest(source)
    source.write_bytes(source.read_bytes() + b"tampered")
    with pytest.raises(ValueError, match="SHA256|size"):
        check(source, m)


def test_wrong_artifact_basename_or_legacy_html_rejected(source):
    m = manifest(source)
    m["source"]["name"] = "../repair.csv"
    with pytest.raises(ValueError):
        check(source, m)
    m = manifest(source)
    m["source"]["source_url"] = "https://www.valuebetennis.com/tournaments/2024/02/archive.htm"
    with pytest.raises(ValueError, match="legacy|index|HTML"):
        check(source, m)


def test_bad_sha_and_future_capture_time_rejected(source):
    m = manifest(source)
    m["permission"]["report_sha256"] = "not-a-sha"
    with pytest.raises(ValueError):
        check(source, m)
    m = manifest(source)
    m["source"]["retrieved_at_utc"] = "2029-01-01T00:00:00Z"
    with pytest.raises(ValueError, match="future|as-of"):
        check(source, m)


def test_unreadable_artifact_fails_closed(source):
    m = manifest(source)
    source.unlink()
    with pytest.raises(ValueError):
        check(source, m)


def test_false_rights_fields_cannot_promote_reviewed_status(source):
    m = manifest(source)
    m["permission"]["ai_training_allowed"] = False
    result = check(source, m, trusted={"permission-001": "a" * 64})
    assert result["status"] == "NO_AUTHORIZED_HISTORICAL_REPAIR_SOURCE"


def test_incomplete_draw_flags_even_with_rights_stay_quarantined(source):
    m = manifest(source)
    m["draw_review"]["complete_main_draw"] = False
    r = check(source, m, trusted={"permission-001": "a" * 64})
    assert r["eligible_for_model_training"] == 0
    assert r["main_draw_verified"] is False
