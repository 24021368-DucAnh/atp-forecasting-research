"""Synthetic-only P3 quote receipt and prematch timing contracts."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from atp_gate.quote_receipt import audit_quote_receipt

T = datetime(2027, 1, 20, 9, tzinfo=timezone.utc)


def receipt():
    return {
        "fixture": {
            "match_id": "ATP-2027-001",
            "player_a_id": "ATP-A-001",
            "player_b_id": "ATP-B-002",
            "scheduled_start": (T + timedelta(hours=2)).isoformat(),
            "actual_first_serve": (T + timedelta(hours=2, minutes=5)).isoformat(),
            "start_confirmed": True,
            "status": "SCHEDULED",
        },
        "quote": {
            "match_id": "ATP-2027-001",
            "player_a_id": "ATP-A-001",
            "player_b_id": "ATP-B-002",
            "quote_id": "verified-quote-001",
            "bookmaker": "test-bookmaker",
            "provider_url": "https://example.org/independent-receipt",
            "market": "MATCH_WINNER",
            "odds_a": "1.90",
            "odds_b": "2.05",
            "published_at": (T - timedelta(minutes=6)).isoformat(),
            "observed_at": (T - timedelta(minutes=5)).isoformat(),
            "retrieved_at": (T - timedelta(minutes=4)).isoformat(),
            "market_status": "ACTIVE",
            "retirement_rule": "RETIREMENT_VOID",
        },
        "receipt": {
            "report_id": "receipt-001",
            "report_sha256": "a" * 64,
            "source_rights_reviewed": True,
        },
    }


def check(s, trust=None):
    return audit_quote_receipt(s, as_of=T, trusted_receipts=trust)


def test_mechanically_valid_quote_without_independent_receipt_cannot_claim_t60():
    report = check(receipt())
    assert report["status"] == "NO_TRUSTED_T60_SOURCE"
    assert report["observed_quote_mechanics_ok"] is True
    assert report["independent_receipt_matched"] is False
    assert report["t60_execution_verified"] is False
    assert report["allocation_enabled"] is False and report["stake"] == 0


def test_independent_receipt_match_remains_paper_only():
    report = check(receipt(), {"receipt-001": "a" * 64})
    assert report["status"] == "QUOTE_REVIEW_ONLY"
    assert report["independent_receipt_matched"] is True
    assert report["market_edge_verified"] is False
    assert report["t60_execution_verified"] is False
    assert report["allocation_enabled"] is False and report["stake"] == 0


@pytest.mark.parametrize("mutation,reason", [
    (lambda s: s["quote"].update(observed_at=(T + timedelta(seconds=1)).isoformat()), "QUOTE_NOT_ASOF"),
    (lambda s: s["quote"].update(observed_at=(T - timedelta(hours=1)).isoformat(),
                                 published_at=(T - timedelta(hours=1, minutes=1)).isoformat(),
                                 retrieved_at=(T - timedelta(minutes=4)).isoformat()), "QUOTE_STALE"),
    (lambda s: s["quote"].update(market_status="SUSPENDED"), "MARKET_NOT_ACTIVE"),
    (lambda s: s["quote"].update(market_status="REVOKED"), "MARKET_NOT_ACTIVE"),
    (lambda s: s["quote"].update(player_a_id="ATP-B-002"), "PLAYER_ODDS_ALIGNMENT_CONFLICT"),
    (lambda s: s["fixture"].update(start_confirmed=False), "START_UNCONFIRMED"),
    (lambda s: s["fixture"].update(status="STARTED"), "NOT_PREMATCH"),
    (lambda s: s["quote"].update(retirement_rule="UNKNOWN"), "SETTLEMENT_RULE_UNKNOWN"),
    (lambda s: s["fixture"].update(scheduled_start=(T + timedelta(minutes=40)).isoformat()), "INSIDE_T60_CUTOFF"),
    (lambda s: s["fixture"].update(actual_first_serve=None), "ACTUAL_START_UNVERIFIED"),
    (lambda s: s["fixture"].update(actual_first_serve=(T + timedelta(minutes=40)).isoformat()), "ACTUAL_START_INSIDE_T60"),
])
def test_quote_receipt_rejects_mismatched_or_unavailable_evidence(mutation, reason):
    s = receipt()
    mutation(s)
    out = check(s, {"receipt-001": "a" * 64})
    assert out["status"] == "QUOTE_REJECTED"
    assert reason in out["reasons"]
    assert out["stake"] == 0


def test_wrong_receipt_hash_never_trusted():
    s = receipt()
    out = check(s, {"receipt-001": "b" * 64})
    assert out["status"] == "NO_TRUSTED_T60_SOURCE"
    assert out["independent_receipt_matched"] is False


def test_noncanonical_both_sides_or_bad_overround_rejected():
    s = receipt()
    s["quote"]["odds_a"] = "1.01"
    s["quote"]["odds_b"] = "1.01"
    out = check(s)
    assert "ODDS_OVERROUND_INVALID" in out["reasons"]


def test_naive_asof_and_missing_exact_fields_are_rejected():
    s = receipt()
    with pytest.raises(ValueError):
        audit_quote_receipt(s, as_of=T.replace(tzinfo=None))
    s = receipt()
    del s["quote"]["quote_id"]
    with pytest.raises(ValueError):
        check(s)


@pytest.mark.parametrize("other", [" P1", "P1 ", " P1 ", "P1\n"])
def test_same_player_with_padded_identity_rejected(other):
    s = receipt()
    for part in ("fixture", "quote"):
        s[part].update(player_a_id="P1", player_b_id=other)
    with pytest.raises(ValueError):
        check(s, {"receipt-001": "a" * 64})


@pytest.mark.parametrize("part,field", [
    ("fixture", "match_id"), ("quote", "match_id"),
    ("fixture", "player_a_id"), ("quote", "player_b_id"),
    ("quote", "quote_id"), ("receipt", "report_id"),
])
def test_noncanonical_identity_rejected_even_if_not_a_player_collision(part, field):
    s = receipt()
    s[part][field] += " "
    with pytest.raises(ValueError):
        check(s, {"receipt-001": "a" * 64})


def test_old_publication_recent_observation_is_review_only_not_execution():
    s = receipt()
    s["quote"]["published_at"] = (T - timedelta(days=30)).isoformat()
    out = check(s, {"receipt-001": "a" * 64})
    assert out["status"] == "QUOTE_REVIEW_ONLY"
    assert out["t60_execution_verified"] is False
    assert out["allocation_enabled"] is False and out["stake"] == 0
