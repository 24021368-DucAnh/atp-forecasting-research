"""P1.4c: review legacy Valuebetennis *tournament index* metadata only.

This is not match data, rights clearance, player identity, draw completeness,
or a source eligible for model training.
"""
from __future__ import annotations

from datetime import date, timedelta

from .official_calendar_coverage import (
    _date, _matches_city, audit_official_calendar_coverage,
)
from .valuebetennis_source import _positive_id

_VERSION = "P1_LEGACY_INDEX_CROSSWALK_1"
_ARCHIVE_URL = "https://www.valuebetennis.com/tournaments/2024/02/archive.htm"


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be nonempty text")
    return value.strip()


def audit_legacy_archive_crosswalk(
    inventory: dict,
    official_calendar: dict,
    legacy_manifest: dict,
    *,
    inventory_sha256: str,
) -> dict:
    """Cross-reference *metadata* from the legacy index to official ATP events.

    Every result remains UNVERIFIED: the historical HTML index is not included
    in the modern CC BY 4.0 downloadable CSV rights statement by implication.
    """
    base = audit_official_calendar_coverage(
        inventory, official_calendar, inventory_sha256=inventory_sha256
    )
    if not isinstance(legacy_manifest, dict):
        raise ValueError("legacy manifest must be an object")
    if legacy_manifest.get("manifest_version") != _VERSION:
        raise ValueError("unknown legacy archive manifest version")
    if legacy_manifest.get("inventory_sha256") != inventory_sha256:
        raise ValueError("legacy manifest does not match pinned source snapshot")
    if legacy_manifest.get("archive_url") != _ARCHIVE_URL:
        raise ValueError("legacy archive URL must match reviewed historical index")
    if legacy_manifest.get("archive_record_type") != "HISTORICAL_TOURNAMENT_INDEX_ONLY":
        raise ValueError("legacy archive contains only an event index, not match data")
    if legacy_manifest.get("archive_page_rights") != "UNVERIFIED_NOT_CSV_CC_BY_GRANT":
        raise ValueError("legacy HTML rights are not covered by the CSV CC BY grant")

    entries = legacy_manifest.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("legacy manifest requires tournament metadata entries")

    official = {event["event_key"]: event for event in base["events"]}
    seen_keys: set[str] = set()
    seen_ids: set[str] = set()
    source_ids: set[str] = set()
    for source_group in inventory["tournament_inventory"]["tournament_seasons"]:
        source_ids.add(source_group["tournament_id"])

    result = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("legacy index row must be an object")
        key = _text(entry.get("official_event_key"), "official_event_key")
        if key not in official:
            raise ValueError("legacy event key absent from official ATP reference")
        if key in seen_keys:
            raise ValueError("duplicate official event key in legacy index")
        seen_keys.add(key)

        provider_id = _positive_id(entry.get("legacy_provider_tournament_id"))
        if provider_id is None:
            raise ValueError("invalid positive legacy provider tournament ID")
        if provider_id in seen_ids:
            raise ValueError("duplicate legacy provider tournament ID")
        if provider_id in source_ids:
            raise ValueError("legacy provider tournament ID is present in source inventory")
        seen_ids.add(provider_id)

        original_name = _text(entry.get("legacy_tournament_name"), "legacy_tournament_name")
        reference = official[key]
        if not _matches_city(reference["city"], [original_name]):
            raise ValueError("legacy city suffix inconsistent with official ATP city")

        index_date = _date(entry.get("legacy_start_date"), "legacy_start_date")
        official_start = date.fromisoformat(reference["official_start_date"])
        official_end = date.fromisoformat(reference["official_end_date"])
        if (
            index_date.year != reference["official_year"]
            or not official_start - timedelta(days=4)
            <= index_date <= official_end + timedelta(days=4)
        ):
            raise ValueError("legacy date inconsistent with official ATP event window")
        if entry.get("legacy_sex_marker") != "H":
            raise ValueError("legacy index row is not men's event metadata")
        if entry.get("legacy_category") != "Main tour":
            raise ValueError("legacy index row not labelled top-level Main tour")
        if entry.get("evidence_url") != _ARCHIVE_URL:
            raise ValueError("legacy evidence URL must be the reviewed archive index")

        result.append({
            "official_event_key": key,
            "official_year": reference["official_year"],
            "official_event_name": reference["official_event_name"],
            "official_tier_from_atp_reference": reference["official_tier"],
            "legacy_provider_tournament_id": provider_id,
            "legacy_tournament_name": original_name,
            "legacy_start_date": index_date.isoformat(),
            "legacy_category_original": entry["legacy_category"],
            "legacy_sex_marker_original": entry["legacy_sex_marker"],
            "archive_record_type": "TOURNAMENT_INDEX_ONLY",
            "source_status": reference["status"],
            "licensed_match_rows": 0,
            "event_identity_verified": False,
            "main_draw_verified": False,
        })

    if seen_keys != set(official):
        missing = sorted(set(official) - seen_keys)
        raise ValueError(f"legacy crosswalk is missing official ATP events: {missing}")

    result.sort(key=lambda item: (item["legacy_start_date"], item["official_event_key"]))
    return {
        "status": "LEGACY_CROSSWALK_REVIEW_REQUIRED",
        "mode": "HISTORICAL_RESEARCH_ONLY",
        "crosswalk_version": "P1_LEGACY_INDEX_AUDIT_1",
        "source_inventory_sha256": inventory_sha256,
        "archive_index_url": _ARCHIVE_URL,
        "official_event_count": base["official_event_count"],
        "crosswalk_entries": len(result),
        "archive_ids_absent_from_source": len(seen_ids),
        "entries": result,
        "warnings": [
            "LEGACY_INDEX_ONLY_NOT_MATCH_LEVEL_DATA",
            "LEGACY_HTML_RIGHTS_NOT_ESTABLISHED_BY_CSV_LICENSE",
            "ARCHIVE_TOURNAMENT_ID_NOT_VERIFIED_MATCH_IDENTITY",
            "MISSING_2024_FEB_MATCH_RESULTS_NOT_RESTORED",
            "OFFICIAL_MAIN_DRAW_AND_SOURCE_COMPLETENESS_UNVERIFIED",
            "NO_T60_PRICE_SNAPSHOTS",
        ],
        "legacy_archive_rights_verified": False,
        "legacy_match_results_available": False,
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
