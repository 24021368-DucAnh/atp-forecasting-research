"""Explicit, evidence-linked ATP tier claims for a pinned historical source snapshot.

An evidence URL is a provenance claim, NOT independent automatic verification.
This audit never authorises Valuebetennis input for training or allocation.
"""
from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any
from urllib.parse import urlsplit

from .inventory_review import review_tournament_inventory

_VERSION = "P1_EDITION_TIER_REGISTRY_1"
_TIERS = {"ATP_250", "ATP_500", "MASTERS_1000", "GRAND_SLAM", "OTHER"}
_POTENTIAL_TARGET = {"ATP_500", "MASTERS_1000", "GRAND_SLAM"}
_QUALITY = {"UNVERIFIED", "KNOWN_INCOMPLETE"}
_OFFICIAL_HOSTS = {
    "atptour.com", "www.atptour.com", "ausopen.com", "www.ausopen.com",
    "rolandgarros.com", "www.rolandgarros.com",
    "wimbledon.com", "www.wimbledon.com",
    "usopen.org", "www.usopen.org", "itftennis.com", "www.itftennis.com",
    "olympics.com", "www.olympics.com",
}


def _obj(value: Any, label: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _list(value: Any, label: str) -> list:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    return value


def _year(value: Any, label: str) -> int:
    if type(value) is not int or not 1900 <= value <= 2100:
        raise ValueError(f"invalid {label}; expected 1900..2100")
    return value


def _id(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.isascii() or not value.isdecimal() or int(value) < 1:
        raise ValueError(f"invalid {label}; expected positive integer string")
    return value


def _str(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")
    return value.strip()


def _digest(value: Any) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("inventory SHA-256 must be 64 lowercase hex characters")
    return value


def _evidence_url(value: Any) -> str:
    url = _str(value, "evidence_url")
    try:
        p = urlsplit(url)
        hostname = p.hostname
        port = p.port
    except ValueError as exc:
        raise ValueError("invalid evidence URL") from exc
    if (p.scheme != "https" or hostname not in _OFFICIAL_HOSTS
        or p.username or p.password or port not in (None, 443)
        or not p.path.strip("/") or p.fragment):
        raise ValueError("evidence_url must use an allowed official HTTPS source with a path")
    return url


def _review_date(value: Any) -> str:
    text = _str(value, "reviewed_on")
    try:
        parsed = date.fromisoformat(text)
        if parsed.isoformat() != text:
            raise ValueError
    except ValueError as exc:
        raise ValueError("reviewed_on must be an ISO calendar date") from exc
    return text


def audit_tier_registry(
    inventory: dict, registry: dict, *, inventory_sha256: str
) -> dict:
    """Validate explicitly evidenced per-UTC-year provider tier claims.

    No tier, round, edition, or coverage is inferred from provider names.
    All event claims remain research review only, never trainable data.
    """
    # Reuse P1.3b's full invariants and event count reconciliation.
    baseline = review_tournament_inventory(inventory)
    source_hash = _digest(inventory_sha256)
    registry = _obj(registry, "registry")
    if registry.get("registry_version") != _VERSION:
        raise ValueError("unknown edition tier registry version")
    if _digest(registry.get("inventory_sha256")) != source_hash:
        raise ValueError("source inventory SHA-256 mismatch; review new snapshot")

    groups = inventory["tournament_inventory"]["tournament_seasons"]
    by_key = {(row["year"], row["tournament_id"]): row for row in groups}
    years_by_id: dict[str, set[int]] = {}
    for row in groups:
        years_by_id.setdefault(row["tournament_id"], set()).add(row["year"])

    tier_totals: dict[str, Counter] = {tier: Counter() for tier in sorted(_TIERS)}
    coverage_totals: Counter = Counter()
    reviewed_rows = []
    seen = set()
    potential_target = 0
    known_incomplete_target = 0
    history_only = 0
    excluded = 0
    reviewed_candidate_matches = 0

    for raw in _list(registry.get("entries"), "entries"):
        claim = _obj(raw, "tier registry entry")
        year = _year(claim.get("utc_year"), "utc_year")
        tid = _id(claim.get("tournament_id"), "tournament_id")
        key = (year, tid)
        if key in seen:
            raise ValueError("duplicate per-year tournament ID in tier registry")
        seen.add(key)
        if key not in by_key:
            raise ValueError("registry points to unknown UTC-year provider tournament ID")
        if len(years_by_id[tid]) != 1:
            raise ValueError("cross-year provider tournament ID requires official edition resolution")
        row = by_key[key]
        original_name = _str(claim.get("observed_name"), "observed_name")
        if len(row["names"]) != 1 or row["names"][0] != original_name:
            raise ValueError("observed tournament name does not match pinned inventory")
        if row.get("metadata_conflict") or len(row.get("categories", [])) != 1:
            raise ValueError("conflicted source event metadata cannot be tier classified")
        edition = _year(claim.get("official_edition_year"), "official_edition_year")
        if edition != year:
            raise ValueError("official edition year must be independently resolved; UTC-year mismatch")
        tier = claim.get("official_tier")
        if tier not in _TIERS:
            raise ValueError("invalid official tournament tier")
        quality = claim.get("dataset_coverage")
        if quality not in _QUALITY:
            raise ValueError("full source coverage cannot be certified from this inventory")
        evidence_url = _evidence_url(claim.get("evidence_url"))
        note = _str(claim.get("evidence_note"), "evidence_note")
        reviewed_on = _review_date(claim.get("reviewed_on"))
        count = row["candidate_matches"]
        tier_totals[tier]["event_groups"] += 1
        tier_totals[tier]["candidate_matches"] += count
        coverage_totals[quality] += 1
        reviewed_candidate_matches += count

        if tier == "ATP_250":
            history_only += count
        elif tier == "OTHER":
            excluded += count
        elif tier in _POTENTIAL_TARGET:
            potential_target += count
            if quality == "KNOWN_INCOMPLETE":
                known_incomplete_target += count

        reviewed_rows.append({
            "utc_year": year, "tournament_id": tid,
            "observed_name": original_name, "official_edition_year": edition,
            "official_tier": tier,
            "tier_claim_reviewed": True,
            "dataset_coverage": quality,
            "candidate_matches": count,
            "evidence_url": evidence_url,
            "evidence_note": note, "reviewed_on": reviewed_on,
            "main_draw_verified": False, "eligible_for_model_training": 0,
        })

    absences = []
    seen_absences = set()
    present_years = {int(year) for year in inventory["coverage"]["by_year"]}
    for raw in _list(registry.get("expected_absent_events"), "expected_absent_events"):
        claim = _obj(raw, "missing-event evidence")
        year = _year(claim.get("official_edition_year"), "official_edition_year")
        name = _str(claim.get("official_event_name"), "official_event_name")
        if year not in present_years:
            raise ValueError("cannot assert absent event in an entirely unobserved calendar year")
        abs_key = (year, name.casefold())
        if abs_key in seen_absences:
            raise ValueError("duplicate expected absent event")
        seen_absences.add(abs_key)
        tier = claim.get("official_tier")
        if tier not in _TIERS:
            raise ValueError("invalid official tier for absent event")
        markers = _list(claim.get("match_markers"), "match_markers")
        if not markers or any(
            not isinstance(m, str) or len(m.strip()) < 5 for m in markers
        ):
            raise ValueError("absent-event match_markers must be specific nonempty strings")
        markers_folded = [m.strip().casefold() for m in markers]
        if any(
            marker in n.casefold()
            for row in groups if row["year"] == year
            for n in row["names"] for marker in markers_folded
        ):
            raise ValueError("expected absent event matches an observed source event")
        evidence = _evidence_url(claim.get("evidence_url"))
        reviewed_on = _review_date(claim.get("reviewed_on"))
        absences.append({
            "official_edition_year": year, "official_event_name": name,
            "official_tier": tier, "match_markers": markers,
            "evidence_url": evidence, "reviewed_on": reviewed_on,
            "status": "EXPECTED_EVENT_ABSENT_FROM_SOURCE_INVENTORY",
        })

    total_groups = baseline["integrity"]["tournament_season_groups"]
    total_candidates = baseline["integrity"]["candidate_matches"]
    reviewed_rows.sort(key=lambda row: (row["utc_year"], int(row["tournament_id"])))
    absences.sort(key=lambda row: (row["official_edition_year"], row["official_event_name"]))
    unreviewed_keys = [
        {"utc_year": row["year"], "tournament_id": row["tournament_id"],
         "observed_name": row["names"][0],
         "candidate_matches": row["candidate_matches"]}
        for row in groups if (row["year"], row["tournament_id"]) not in seen
    ]
    unreviewed_keys.sort(key=lambda row: (row["utc_year"], int(row["tournament_id"])))
    assert len(reviewed_rows) + len(unreviewed_keys) == total_groups
    assert reviewed_candidate_matches + sum(r["candidate_matches"] for r in unreviewed_keys) == total_candidates

    return {
        "status": "REVIEW_REQUIRED",
        "mode": "HISTORICAL_RESEARCH_ONLY",
        "audit_version": "P1_EDITION_TIER_AUDIT_1",
        "inventory_sha256": source_hash,
        "registry_version": _VERSION,
        "source_inventory_integrity": "RECONCILED",
        "tournament_season_groups": total_groups,
        "candidate_matches": total_candidates,
        "reviewed_event_groups": len(reviewed_rows),
        "unreviewed_event_groups": len(unreviewed_keys),
        "reviewed_candidate_matches": reviewed_candidate_matches,
        "unreviewed_candidate_matches": total_candidates - reviewed_candidate_matches,
        "reviewed_tiers": {
            tier: {
                "event_groups": int(tier_totals[tier]["event_groups"]),
                "candidate_matches": int(tier_totals[tier]["candidate_matches"]),
            }
            for tier in sorted(_TIERS)
        },
        "dataset_coverage_claims": {
            quality: int(coverage_totals[quality]) for quality in sorted(_QUALITY)
        },
        "history_only_matches": history_only,
        "potential_target_tier_matches": potential_target,
        "known_incomplete_target_matches": known_incomplete_target,
        "reviewed_other_event_matches": excluded,
        "reviewed_event_claims": reviewed_rows,
        "unreviewed_event_keys": unreviewed_keys,
        "expected_absent_event_count": len(absences),
        "expected_absent_events": absences,
        "warnings": [
            "OFFICIAL_SOURCE_URL_SYNTAX_NOT_PROOF_OF_SOURCE_CONTENT",
            "CROSS_YEAR_PROVIDER_IDS_NOT_EDITION_VERIFIED",
            "EVENT_AND_ROUND_COMPLETENESS_NOT_VERIFIED",
            "TIER_REVIEW_NOT_MAIN_DRAW_APPROVAL",
            "SOURCE_ODDS_NOT_AUTHENTICATED_T60",
            "NO_TRAINING_OR_ALLOCATION_AUTHORIZATION",
        ],
        "source_file_origin_verified": False,
        "tier_mapping_verified": False,
        "main_draw_verified": False,
        "t60_quote_verified": False,
        "eligible_for_model_training": 0,
        "live_eligible": False,
        "allocation_enabled": False,
        "validation_report_trusted": False,
        "stake": 0,
    }
