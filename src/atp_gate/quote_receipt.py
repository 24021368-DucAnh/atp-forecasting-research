"""Independent T−60 quote-receipt preflight, strictly paper-only.

Checks an observed quote's *claimed* times and identities against a confirmed
fixture. It cannot independently prove a sportsbook offered that price, that
a provider report was authentic, that rights exist, or that bets are profitable.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit

_SHA = re.compile(r"^[0-9a-f]{64}$")
_CUTOFF = timedelta(minutes=60)
_MAX_AGE = timedelta(minutes=30)


def _record(data: object, fields: set[str], title: str) -> dict:
    if not isinstance(data, dict) or set(data) != fields:
        raise ValueError(f"invalid {title} schema")
    return data


def _datetime(value: object, label: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"invalid {label} timestamp")
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid {label} timestamp") from exc
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError(f"{label} timestamp must be timezone aware")
    return instant


def _odds(value: object, label: str) -> Decimal:
    if not isinstance(value, str):
        raise ValueError(f"{label} odds must be an explicit decimal string")
    try:
        out = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"invalid {label} odds") from exc
    if not out.is_finite() or not Decimal("1") < out <= Decimal("1000"):
        raise ValueError(f"invalid {label} odds")
    return out


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"invalid {label} text")
    return value


def audit_quote_receipt(
    snapshot: dict, *, as_of: datetime,
    trusted_receipts: Mapping[str, str] | None = None,
) -> dict:
    """Audit a synthetic or independently captured quote without approving it.

    The retrospective actual-first-serve field is intentionally NEVER an
    input to a prematch prediction, only an after-the-event audit datum.
    """
    if not isinstance(as_of, datetime) or as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("evaluation as-of must be timezone-aware")
    source = _record(snapshot, {"fixture", "quote", "receipt"}, "receipt snapshot")
    fixture = _record(source["fixture"], {
        "match_id", "player_a_id", "player_b_id", "scheduled_start",
        "actual_first_serve", "start_confirmed", "status",
    }, "fixture")
    quote = _record(source["quote"], {
        "match_id", "player_a_id", "player_b_id", "quote_id",
        "bookmaker", "provider_url", "market", "odds_a", "odds_b",
        "published_at", "observed_at", "retrieved_at",
        "market_status", "retirement_rule",
    }, "quote")
    receipt = _record(source["receipt"], {
        "report_id", "report_sha256", "source_rights_reviewed",
    }, "independent receipt")

    for field in ("match_id", "player_a_id", "player_b_id"):
        _text(fixture[field], f"fixture {field}")
        _text(quote[field], f"quote {field}")
    _text(quote["quote_id"], "quote identifier")
    _text(quote["bookmaker"], "bookmaker")
    report_id = _text(receipt["report_id"], "receipt report ID")
    report_sha = receipt["report_sha256"]
    if not isinstance(report_sha, str) or not _SHA.fullmatch(report_sha):
        raise ValueError("invalid independent receipt report SHA256")
    if type(receipt["source_rights_reviewed"]) is not bool:
        raise ValueError("rights marker must be boolean")
    url = quote["provider_url"]
    if not isinstance(url, str) or urlsplit(url).scheme != "https" or not urlsplit(url).hostname:
        raise ValueError("provider source URL must be HTTPS")

    scheduled = _datetime(fixture["scheduled_start"], "scheduled start")
    actual = None
    if fixture["actual_first_serve"] is not None:
        actual = _datetime(fixture["actual_first_serve"], "actual first serve")
    published = _datetime(quote["published_at"], "published")
    observed = _datetime(quote["observed_at"], "observed")
    retrieved = _datetime(quote["retrieved_at"], "retrieved")
    a = _odds(quote["odds_a"], "A")
    b = _odds(quote["odds_b"], "B")
    overround = Decimal("1") / a + Decimal("1") / b

    reasons: list[str] = []
    if (fixture["match_id"] != quote["match_id"]):
        reasons.append("MATCH_ID_CONFLICT")
    if (fixture["player_a_id"], fixture["player_b_id"]) != (
            quote["player_a_id"], quote["player_b_id"]):
        reasons.append("PLAYER_ODDS_ALIGNMENT_CONFLICT")
    if fixture["player_a_id"] == fixture["player_b_id"]:
        reasons.append("PLAYER_ID_CONFLICT")
    if type(fixture["start_confirmed"]) is not bool or not fixture["start_confirmed"]:
        reasons.append("START_UNCONFIRMED")
    if fixture["status"] not in ("SCHEDULED", "DELAYED"):
        reasons.append("NOT_PREMATCH")
    if scheduled - as_of < _CUTOFF:
        reasons.append("INSIDE_T60_CUTOFF")
    if actual is None:
        reasons.append("ACTUAL_START_UNVERIFIED")
    elif actual - as_of < _CUTOFF:
        reasons.append("ACTUAL_START_INSIDE_T60")
    if not (published <= observed <= retrieved <= as_of):
        reasons.append("QUOTE_NOT_ASOF")
    if observed <= as_of and as_of - observed > _MAX_AGE:
        reasons.append("QUOTE_STALE")
    if quote["market"] != "MATCH_WINNER":
        reasons.append("UNSUPPORTED_MARKET")
    if quote["market_status"] != "ACTIVE":
        reasons.append("MARKET_NOT_ACTIVE")
    if quote["retirement_rule"] not in ("RETIREMENT_ACTION", "RETIREMENT_VOID"):
        reasons.append("SETTLEMENT_RULE_UNKNOWN")
    if not Decimal("0.90") <= overround <= Decimal("1.35"):
        reasons.append("ODDS_OVERROUND_INVALID")

    trusted = trusted_receipts or {}
    independent = (
        trusted.get(report_id) == report_sha
        and receipt["source_rights_reviewed"] is True
    )
    if reasons:
        status = "QUOTE_REJECTED"
    elif independent:
        status = "QUOTE_REVIEW_ONLY"
    else:
        status = "NO_TRUSTED_T60_SOURCE"
    return {
        "status": status,
        "mode": "HISTORICAL_RESEARCH_ONLY",
        "reasons": sorted(set(reasons)),
        "quote_id": quote["quote_id"],
        "observed_quote_mechanics_ok": not bool(reasons),
        "independent_receipt_matched": independent,
        "t60_execution_verified": False,
        "market_edge_verified": False,
        "asof_feature_provenance_verified": False,
        "validation_report_trusted": False,
        "allocation_enabled": False,
        "live_eligible": False,
        "stake": 0,
        "warnings": [
            "RECEIPT_IDENTITY_IS_NOT_INDEPENDENT_PROOF_OF_OFFER_AVAILABILITY",
            "HISTORICAL_RESULTS_AND_T60_EXECUTION_NOT_CERTIFIED",
            "PAPER_ONLY_NO_LIVE_ALLOCATION",
        ],
    }
