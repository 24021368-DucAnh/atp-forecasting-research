"""Forensic local-only Valuebetennis CSV audit for missing official calendar events.

This diagnostic investigates raw provider rows and why provisional ATP
selection filters excluded them. It cannot establish complete tournament
identity, draw eligibility, actual start time or tradable odds.
"""
from __future__ import annotations

from collections import Counter
import csv
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from .official_calendar_coverage import (
    _matches_city, _normalized_city, audit_official_calendar_coverage
)
from .valuebetennis_source import (
    _CATEGORIES, _REQUIRED, _positive_id, _sha256_and_length, _utc
)


def _parse_month(month: str) -> tuple[int, int]:
    if not isinstance(month, str) or len(month) != 7:
        raise ValueError("month must be YYYY-MM")
    try:
        parsed = date.fromisoformat(month + "-01")
    except ValueError as exc:
        raise ValueError("month must be YYYY-MM with a real calendar month") from exc
    if parsed.strftime("%Y-%m") != month:
        raise ValueError("month must be canonical YYYY-MM")
    return parsed.year, parsed.month


def _reason(row: dict, seen: set[str], utc_time) -> str:
    """Mirrors the original provisional-source gate order (P1.2)."""
    if None in row:
        return "MALFORMED_ROW"
    genre = str(row["genre"] or "").strip().casefold()
    if genre != "atp":
        return "EXCLUDED_WTA" if genre == "wta" else "EXCLUDED_OTHER_GENRE"
    category = _CATEGORIES.get(str(row["categorie"] or "").strip().casefold())
    if category is None:
        return "EXCLUDED_OTHER_CATEGORY"

    match_id = _positive_id(row["match_id"])
    player1 = _positive_id(row["joueur1_id"])
    player2 = _positive_id(row["joueur2_id"])
    if not match_id or not player1 or not player2 or player1 == player2:
        return "INVALID_IDENTITY"
    winner = _positive_id(row["vainqueur_id"])
    if winner not in (player1, player2):
        return "INVALID_WINNER"
    try:
        raw_round = str(row["tour"] or "").strip()
        numeric_round = int(raw_round)
        if str(numeric_round) != raw_round or not 0 <= numeric_round <= 12:
            raise ValueError
    except ValueError:
        return "INVALID_ROUND"
    if utc_time is None:
        return "INVALID_DATE"
    if not str(row["joueur1"] or "").strip() or not str(row["joueur2"] or "").strip():
        return "INVALID_IDENTITY"
    if match_id in seen:
        return "DUPLICATE_MATCH_ID"
    seen.add(match_id)
    return "ACCEPTED_PROVISIONAL"


def audit_source_gap(
    csv_path: str | Path,
    inventory: dict,
    official_calendar: dict,
    *,
    inventory_sha256: str,
    month: str,
) -> dict:
    """Review ONE local file, bound to the original five-season inventory digest."""
    year, requested_month = _parse_month(month)
    calendar_audit = audit_official_calendar_coverage(
        inventory, official_calendar, inventory_sha256=inventory_sha256,
    )
    official_events = calendar_audit["events"]
    if any(event["official_year"] != year for event in official_events):
        raise ValueError("requested month year does not match all official events")

    path = Path(csv_path)
    if path.suffix.lower() != ".csv":
        raise ValueError("raw source must be one local semicolon-separated .csv")
    manifest = inventory.get("source_files")
    if not isinstance(manifest, list):
        raise ValueError("pinned inventory has no source file manifest")
    matching = [x for x in manifest if isinstance(x, dict) and x.get("name") == path.name]
    if len(matching) != 1:
        raise ValueError("raw CSV basename missing or ambiguous in inventory manifest")
    actual_hash, actual_size = _sha256_and_length(path)
    expected = matching[0]
    if (actual_hash != expected.get("sha256") or actual_size != expected.get("size_bytes")):
        raise ValueError("raw CSV SHA256/size does not match pinned inventory")

    by_source = inventory.get("coverage", {}).get("by_source")
    if not isinstance(by_source, dict) or type(by_source.get(path.name)) is not int:
        raise ValueError("pinned inventory lacks accepted rows by source")
    expected_accepted = by_source[path.name]

    total_rows = 0
    accepted = 0
    accepted_month = 0
    raw_month_rows = 0
    undated_rows = 0
    all_reasons: Counter[str] = Counter()
    month_reasons: Counter[str] = Counter()
    by_genre: Counter[str] = Counter()
    by_raw_category: Counter[str] = Counter()
    seen_match_ids: set[str] = set()

    event_hits: dict[str, dict] = {
        entry["event_key"]: {
            "event_key": entry["event_key"],
            "official_event_name": entry["official_event_name"],
            "city": entry["city"],
            "official_tier": entry["official_tier"],
            "raw_city_date_rows": 0,
            "accepted_provisional_city_date_rows": 0,
            "rejection_reasons": Counter(),
        }
        for entry in official_events
    }
    ranges = {
        entry["event_key"]: (
            date.fromisoformat(entry["official_start_date"]) - timedelta(days=4),
            date.fromisoformat(entry["official_end_date"]) + timedelta(days=4),
        )
        for entry in official_events
    }

    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = csv.DictReader(stream, delimiter=";")
        if rows.fieldnames is None or not _REQUIRED.issubset(rows.fieldnames):
            absent = sorted(_REQUIRED - set(rows.fieldnames or []))
            raise ValueError(f"raw source missing required CSV columns: {absent}")
        for row in rows:
            total_rows += 1
            when = _utc(row.get("date"))
            if when is None:
                undated_rows += 1
            reason = _reason(row, seen_match_ids, when)
            all_reasons[reason] += 1
            if reason == "ACCEPTED_PROVISIONAL":
                accepted += 1

            in_month = when is not None and when.year == year and when.month == requested_month
            if in_month:
                raw_month_rows += 1
                genre = str(row.get("genre") or "").strip().casefold()
                bucket = genre if genre in ("atp", "wta") else "other"
                by_genre[bucket] += 1
                if bucket == "atp":
                    by_raw_category[str(row.get("categorie") or "").strip() or "UNKNOWN"] += 1
                month_reasons[reason] += 1
                if reason == "ACCEPTED_PROVISIONAL":
                    accepted_month += 1

            if when is None or not isinstance(row.get("tournoi"), str):
                continue
            # A strict city suffix + approximate date is NOT verified event identity.
            for event in official_events:
                if when.year != event["official_year"]:
                    continue
                low, high = ranges[event["event_key"]]
                if not low <= when.date() <= high:
                    continue
                if not _matches_city(event["city"], [row["tournoi"]]):
                    continue
                hit = event_hits[event["event_key"]]
                hit["raw_city_date_rows"] += 1
                if reason == "ACCEPTED_PROVISIONAL":
                    hit["accepted_provisional_city_date_rows"] += 1
                else:
                    hit["rejection_reasons"][reason] += 1

    if accepted != expected_accepted:
        raise ValueError(
            f"accepted source rows do not reconcile with pinned by_source: "
            f"{accepted} != {expected_accepted}"
        )
    diagnostics = []
    for event in official_events:
        hit = event_hits[event["event_key"]]
        if hit["accepted_provisional_city_date_rows"]:
            status = "ACCEPTED_SOURCE_CANDIDATE_PRESENT"
        elif hit["raw_city_date_rows"]:
            status = "ONLY_FILTERED_RAW_CANDIDATES"
        else:
            status = "NO_MATCHING_RAW_CITY_DATE_ROWS"
        diagnostics.append({
            **hit,
            "status": status,
            "rejection_reasons": dict(sorted(hit["rejection_reasons"].items())),
            "event_identity_verified": False,
            "main_draw_verified": False,
        })

    status_counts = Counter(event["status"] for event in diagnostics)
    return {
        "status": "RAW_SOURCE_FORENSIC_REVIEW_REQUIRED",
        "mode": "HISTORICAL_RESEARCH_ONLY",
        "forensic_version": "P1_RAW_SOURCE_GAP_FORENSIC_1",
        "source_scope": "ONE_LOCAL_CSV_ONLY",
        "inventory_sha256": inventory_sha256,
        "source_file": {
            "name": path.name, "sha256": actual_hash, "size_bytes": actual_size,
            "matches_pinned_inventory_manifest": True,
        },
        "source_total_rows": total_rows,
        "source_provisional_accepted": accepted,
        "source_expected_accepted": expected_accepted,
        "source_rejection_counts": dict(sorted(
            (key, int(value)) for key, value in all_reasons.items()
            if key != "ACCEPTED_PROVISIONAL"
        )),
        "month": {
            "year_month": month,
            "raw_rows": raw_month_rows,
            "by_genre": dict(sorted(by_genre.items())),
            "atp_by_raw_category": dict(sorted(by_raw_category.items())),
            "filter_reasons": dict(sorted(month_reasons.items())),
            "accepted_provisional": accepted_month,
        },
        "undated_rows_outside_month_attribution": undated_rows,
        "official_event_count": len(diagnostics),
        "official_event_status_counts": dict(sorted(status_counts.items())),
        "official_event_diagnostics": diagnostics,
        "warnings": [
            "LOCAL_FILE_HASH_MATCH_DOES_NOT_AUTHENTICATE_PROVIDER_ORIGIN",
            "ONE_LOCAL_SOURCE_FILE_NOT_ALL_PROVIDER_SEASONS",
            "CITY_NAME_MATCH_IS_NOT_EXHAUSTIVE",
            "BAD_DATE_ROWS_CANNOT_BE_ATTRIBUTED_TO_A_MONTH",
            "SOURCE_EVENT_ID_AND_MAIN_DRAW_NOT_VERIFIED",
            "OPENING_CLOSING_ODDS_NOT_AUTHENTICATED_T60",
            "NO_MISSING_MATCHES_INFERRED_OR_IMPORTED",
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
