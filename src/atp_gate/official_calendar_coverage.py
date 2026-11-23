"""Compare curated ATP official event expectations with a pinned source inventory.

A venue/date hit is a *candidate to review*, not verified event identity.
No model eligibility, real stakes or certified match completeness are created.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
from typing import Any
import unicodedata

from .inventory_review import review_tournament_inventory
from .tier_registry import _digest, _evidence_url, _review_date, _year

_VERSION = "P1_OFFICIAL_EVENT_CALENDAR_1"
_TIERS = {"ATP_250", "ATP_500", "MASTERS_1000", "GRAND_SLAM"}
_MARGIN = timedelta(days=4)


def _text(raw: Any, label: str) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"{label} must be nonempty text")
    return raw.strip()


def _date(raw: Any, label: str) -> date:
    value = _text(raw, label)
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"invalid ISO date for {label}") from error
    if parsed.isoformat() != value:
        raise ValueError(f"invalid ISO date for {label}")
    return parsed


def _normalized_city(raw: str) -> str:
    normal = unicodedata.normalize("NFKD", raw)
    return " ".join(
        "".join(char for char in normal if not unicodedata.combining(char))
        .casefold().split()
    )


def _matches_city(event_city: str, source_names: Any) -> bool:
    if not isinstance(source_names, list):
        raise ValueError("source tournament names must be an array")
    normalized = _normalized_city(event_city)
    return any(
        isinstance(name, str)
        and " - " in name
        and _normalized_city(name.rsplit(" - ", 1)[-1]) == normalized
        for name in source_names
    )


def audit_official_calendar_coverage(
    inventory: dict, official_calendar: dict, *, inventory_sha256: str,
) -> dict:
    """Find possible missing/ambiguous source events using independently curated references.

    The returned statuses are limited to absence or *unverified* city/date
    candidate matches. This function cannot grant any model/market permissions.
    """
    baseline = review_tournament_inventory(inventory)
    source_hash = _digest(inventory_sha256)
    if not isinstance(official_calendar, dict):
        raise ValueError("official_calendar must be JSON object")
    if official_calendar.get("calendar_version") != _VERSION:
        raise ValueError("unknown official calendar schema version")
    if official_calendar.get("scope") != "CURATED_OFFICIAL_EVENTS_ONLY":
        raise ValueError("calendar must explicitly limit its scope")
    if _digest(official_calendar.get("inventory_sha256")) != source_hash:
        raise ValueError("official calendar pinned inventory SHA256 mismatch")

    entries = official_calendar.get("events")
    if not isinstance(entries, list) or not entries:
        raise ValueError("official calendar events must be a nonempty list")

    groups = inventory["tournament_inventory"]["tournament_seasons"]
    seen_events: set[str] = set()
    seen_date_city: set[tuple[int, str, str, str]] = set()
    result_events = []
    by_tier = Counter()
    missing_by_tier = Counter()
    missing_by_month = Counter()
    possible_count = 0
    ambiguous_count = 0

    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("official calendar event must be an object")
        event_key = _text(entry.get("event_key"), "event_key")
        if not event_key.startswith("ATP_") or event_key in seen_events:
            raise ValueError("duplicate/invalid official event_key")
        seen_events.add(event_key)
        year = _year(entry.get("official_year"), "official_year")
        name = _text(entry.get("official_event_name"), "official_event_name")
        city = _text(entry.get("city"), "city")
        tier = entry.get("official_tier")
        if tier not in _TIERS:
            raise ValueError("unrecognized ATP event tier")
        start = _date(entry.get("start_date"), "start_date")
        end = _date(entry.get("end_date"), "end_date")
        if (year != start.year or year != end.year
            or end < start or (end - start).days > 30):
            raise ValueError("official event year and date window inconsistent")
        unique_key = (year, _normalized_city(city), start.isoformat(), end.isoformat())
        if unique_key in seen_date_city:
            raise ValueError("duplicate official city and date range")
        seen_date_city.add(unique_key)

        results_url = _evidence_url(entry.get("results_archive_url"))
        tier_url = _evidence_url(entry.get("tier_source_url"))
        review_date = _review_date(entry.get("reviewed_on"))

        candidates = []
        for row in groups:
            if row["year"] != year or not _matches_city(city, row["names"]):
                continue
            first = datetime.fromisoformat(row["first_observed_utc"].replace("Z", "+00:00")).date()
            last = datetime.fromisoformat(row["last_observed_utc"].replace("Z", "+00:00")).date()
            if first <= end + _MARGIN and last >= start - _MARGIN:
                candidates.append({
                    "utc_year": row["year"],
                    "tournament_id": row["tournament_id"],
                    "observed_names": list(row["names"]),
                    "candidate_matches": row["candidate_matches"],
                    "first_observed_utc": row["first_observed_utc"],
                    "last_observed_utc": row["last_observed_utc"],
                    "event_identity_verified": False,
                    "main_draw_verified": False,
                })
        candidates.sort(key=lambda x: (x["utc_year"], int(x["tournament_id"])))

        if not candidates:
            status = "NO_SOURCE_EVENT_CANDIDATE"
            missing_by_tier[tier] += 1
            missing_by_month[start.strftime("%Y-%m")] += 1
        elif len(candidates) == 1:
            status = "SOURCE_CANDIDATE_UNVERIFIED"
            possible_count += 1
        else:
            status = "AMBIGUOUS_SOURCE_CANDIDATES"
            ambiguous_count += 1
        by_tier[tier] += 1
        result_events.append({
            "event_key": event_key,
            "official_year": year,
            "official_event_name": name,
            "official_tier": tier,
            "city": city,
            "official_start_date": start.isoformat(),
            "official_end_date": end.isoformat(),
            "results_archive_url": results_url,
            "tier_source_url": tier_url,
            "reviewed_on": review_date,
            "status": status,
            "candidate_source_groups": candidates,
            "candidate_source_matches": sum(r["candidate_matches"] for r in candidates),
            "official_edition_identity_verified": False,
            "match_coverage_verified": False,
        })

    result_events.sort(key=lambda x: (x["official_start_date"], x["event_key"]))
    missing_n = sum(missing_by_tier.values())
    return {
        "status": "COVERAGE_REVIEW_REQUIRED",
        "mode": "HISTORICAL_RESEARCH_ONLY",
        "audit_version": "P1_OFFICIAL_CALENDAR_COVERAGE_1",
        "reference_scope": "CURATED_OFFICIAL_EVENTS_ONLY",
        "inventory_sha256": source_hash,
        "source_inventory_integrity": baseline["integrity"]["status"],
        "source_tournament_groups": baseline["integrity"]["tournament_season_groups"],
        "source_candidate_matches": baseline["integrity"]["candidate_matches"],
        "official_event_count": len(result_events),
        "official_events_by_tier": dict(sorted(by_tier.items())),
        "missing_official_events": missing_n,
        "missing_by_tier": dict(sorted(missing_by_tier.items())),
        "missing_by_official_start_month": dict(sorted(missing_by_month.items())),
        "candidate_official_events": possible_count,
        "ambiguous_official_events": ambiguous_count,
        "events": result_events,
        "warnings": [
            "REFERENCE_LIST_IS_CURATED_NOT_COMPLETE_ATP_CALENDAR",
            "CITY_DATE_MATCH_IS_NOT_VERIFIED_TOURNAMENT_IDENTITY",
            "SOURCE_EVENT_OR_DRAW_COMPLETENESS_NOT_CERTIFIED",
            "OFFICIAL_SCHEDULE_AND_RESULTS_CAN_DIFFER",
            "SOURCE_OPENING_CLOSING_ODDS_ARE_NOT_T60",
            "MISSING_RESULTS_NEVER_IMPUTED",
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
