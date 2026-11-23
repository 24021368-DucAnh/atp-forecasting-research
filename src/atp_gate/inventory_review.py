"""Read-only, fail-closed review of Valuebetennis tournament inventory reports.

No season / tournament / main-draw inference and no model or allocation action.
Source evidence is a *local inventory*, not an authoritative match registry.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

_SPECIAL_NAMES = (
    "atp cup -", "united cup -", "laver cup -", "next gen atp finals -",
    "nitto atp finals -", "olympics -",
)


def _require_int(value: Any, description: str, *, positive: bool = False) -> int:
    if type(value) is not int or value < (1 if positive else 0):
        raise ValueError(f"invalid {description}: requires a nonnegative integer")
    return value


def _require_dict(value: Any, description: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"invalid {description}: expected JSON object")
    return value


def _require_utc(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("invalid observed UTC start timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid observed UTC start timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError("inventory event timestamps must explicitly use UTC")
    return parsed.astimezone(timezone.utc)


def _sorted_counts(rows: Counter) -> dict[str, int]:
    return dict(sorted(rows.items(), key=lambda item: int(item[0])))


def review_tournament_inventory(report: dict) -> dict:
    """Check integrity and flag data-quality risks without approving training."""
    report = _require_dict(report, "report")
    if report.get("mode") != "HISTORICAL_RESEARCH_ONLY":
        raise ValueError("report mode must be historical research only")
    if any(report.get(key) is not False for key in (
        "tier_mapping_verified", "main_draw_verified", "allocation_enabled"
    )):
        raise ValueError("source may not claim verified tier, main draw or allocation")
    if type(report.get("eligible_for_model_training")) is not int or report["eligible_for_model_training"] != 0:
        raise ValueError("source model training eligibility must be zero")
    if type(report.get("stake")) is not int or report["stake"] != 0:
        raise ValueError("source stake must be zero")

    inventory = _require_dict(report.get("tournament_inventory"), "tournament_inventory")
    raw_groups = inventory.get("tournament_seasons")
    if not isinstance(raw_groups, list) or not raw_groups:
        raise ValueError("tournament_seasons must be a nonempty list")
    summary = _require_dict(inventory.get("summary"), "tournament_inventory.summary")
    source_counts = _require_dict(report.get("counts"), "counts")
    coverage = _require_dict(report.get("coverage"), "coverage")

    total_candidates = _require_int(source_counts.get("atp_candidate_matches"), "candidate match count")
    inventory_candidates = _require_int(summary.get("candidate_matches"), "inventory candidate match count")
    inventory_accepted = _require_int(summary.get("inventoried_matches"), "inventoried match count")
    expected_groups = _require_int(summary.get("tournament_seasons"), "tournament group count")
    if not (total_candidates == inventory_candidates == inventory_accepted):
        raise ValueError("candidate/inventory match count reconciliation failed")
    if expected_groups != len(raw_groups):
        raise ValueError("tournament group count reconciliation failed")

    group_year_counts: Counter = Counter()
    match_year_counts: Counter = Counter()
    groups_by_id = defaultdict(list)
    seen_keys = set()
    special_events = []
    missing_final = []
    by_year_event_starts = defaultdict(list)
    accepted_sum = 0

    for group in raw_groups:
        group = _require_dict(group, "tournament_season")
        year = group.get("year")
        if type(year) is not int or not 1900 <= year <= 2100:
            raise ValueError("invalid UTC event year")
        tournament_id = group.get("tournament_id")
        if not (isinstance(tournament_id, str) and tournament_id.isascii()
                and tournament_id.isdecimal() and int(tournament_id) > 0):
            raise ValueError("invalid provider tournament ID")
        key = (year, tournament_id)
        if key in seen_keys:
            raise ValueError("duplicate UTC year and tournament ID")
        seen_keys.add(key)
        names = group.get("names")
        categories = group.get("categories")
        if not isinstance(names, list) or not names or any(not isinstance(n, str) or not n.strip() for n in names):
            raise ValueError("invalid tournament names")
        if not isinstance(categories, list) or not categories or any(not isinstance(c, str) or not c.strip() for c in categories):
            raise ValueError("invalid tournament categories")
        if group.get("main_draw_verified") is not False or group.get("official_tier") is not None:
            raise ValueError("tournament has unsubstantiated official approval")

        count = _require_int(group.get("candidate_matches"), "group candidate matches", positive=True)
        raw_rounds = _require_dict(group.get("round_counts"), "round_counts")
        round_sum = 0
        for round_code, n in raw_rounds.items():
            if not (isinstance(round_code, str) and round_code.isascii()
                    and round_code.isdecimal() and 0 <= int(round_code) <= 12):
                raise ValueError("invalid raw provider round code")
            round_sum += _require_int(n, "round count")
        if round_sum != count:
            raise ValueError("round counts do not reconcile with group matches")

        start = _require_utc(group.get("first_observed_utc"))
        end = _require_utc(group.get("last_observed_utc"))
        if start > end or start.year != year:
            raise ValueError("event date range / UTC year inconsistency")
        group_year_counts[str(year)] += 1
        match_year_counts[str(year)] += count
        groups_by_id[tournament_id].append({
            "year": year, "name": names[0], "candidate_matches": count,
        })
        accepted_sum += count
        by_year_event_starts[year].append((start.date(), names[0], tournament_id))

        event = {
            "year": year, "tournament_id": tournament_id,
            "name": names[0], "categories": categories,
            "candidate_matches": count, "review_only": True,
        }
        is_special = any(
            name.lower().strip().startswith(_SPECIAL_NAMES)
            for name in names
        )
        if is_special:
            special_events.append(event)
        elif ("Grand Slam" in categories or "Masters" in categories) and "12" not in raw_rounds:
            missing_final.append({
                "year": year, "tournament_id": tournament_id,
                "name": names[0], "categories": categories,
                "candidate_matches": count,
                "observed_round_codes": sorted(raw_rounds.keys(), key=int),
                "last_observed_utc": end.isoformat(),
                "interpretation": "RAW_FINAL_CODE_12_ABSENT_NOT_PROOF_OF_MATCH_STATUS",
            })

    if accepted_sum != total_candidates:
        raise ValueError("sum of tournament matches does not reconcile with candidate count")
    reported_year_matches = _require_dict(coverage.get("by_year"), "coverage.by_year")
    reported_year_groups = _require_dict(
        summary.get("tournament_seasons_by_year"), "summary.tournament_seasons_by_year"
    )
    if dict(match_year_counts) != reported_year_matches:
        raise ValueError("accepted match counts by UTC year do not reconcile")
    if dict(group_year_counts) != reported_year_groups:
        raise ValueError("tournament group counts by UTC year do not reconcile")

    cross_year = []
    for tournament_id, rows in groups_by_id.items():
        years = sorted({row["year"] for row in rows})
        if len(years) > 1:
            cross_year.append({
                "tournament_id": tournament_id, "years": years,
                "name_candidates": sorted({row["name"] for row in rows}),
                "candidate_matches": sum(row["candidate_matches"] for row in rows),
                "calendar_year_groups": sorted(rows, key=lambda row: row["year"]),
                "interpretation": "PROVIDER_ID_SPANS_UTC_YEARS_UNVERIFIED_EVENT_EDITION",
            })
    cross_year.sort(key=lambda row: int(row["tournament_id"]))
    special_events.sort(key=lambda row: (row["year"], int(row["tournament_id"])))
    missing_final.sort(key=lambda row: (row["year"], int(row["tournament_id"])))

    in_season_gaps = []
    for year, events in sorted(by_year_event_starts.items()):
        # These are observed *event start records*, not days without any play.
        in_season = sorted(
            (date, name, tid) for date, name, tid in events
            if 1 <= date.month <= 10
        )
        for earlier, later in zip(in_season, in_season[1:]):
            gap = (later[0] - earlier[0]).days
            if gap > 45:
                in_season_gaps.append({
                    "year": year, "days": gap,
                    "from_date": earlier[0].isoformat(),
                    "to_date": later[0].isoformat(),
                    "from_event": earlier[1], "to_event": later[1],
                    "interpretation": "OBSERVED_EVENT_START_GAP_NOT_PROOF_OF_NO_MATCHES",
                })

    return {
        "status": "REVIEW_REQUIRED",
        "mode": "HISTORICAL_RESEARCH_ONLY",
        "review_version": "P1_INVENTORY_REVIEW_1",
        "integrity": {
            "status": "RECONCILED",
            "tournament_season_groups": len(raw_groups),
            "candidate_matches": total_candidates,
            "group_counts_by_utc_year": _sorted_counts(group_year_counts),
            "candidate_matches_by_utc_year": _sorted_counts(match_year_counts),
        },
        "cross_year_tournament_ids": cross_year,
        "special_format_candidates": {
            "group_count": len(special_events),
            "candidate_matches": sum(row["candidate_matches"] for row in special_events),
            "events": special_events,
        },
        "missing_final_code_candidates": missing_final,
        "large_event_start_gaps": in_season_gaps,
        "warnings": [
            "SOURCE_EVENT_EDITION_YEAR_UNVERIFIED",
            "SOURCE_EVENT_AND_ROUND_COVERAGE_NOT_CERTIFIED",
            "SPECIAL_FORMAT_NAMES_REQUIRE_AUTHORITATIVE_SCOPE_REVIEW",
            "YEAR_PRESENCE_NOT_SEASON_COMPLETENESS",
            "PROVIDER_ODDS_NOT_T60",
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
