"""TML main-tour February 2024 historical candidate audit (NONCOMMERCIAL).

This is a read-only provider-specific quality check. It cannot independently
prove official match draw, true match date, model data rights or T-60 odds.
"""
from __future__ import annotations

import csv
import hashlib
import re
from collections import Counter, defaultdict
from pathlib import Path

TML_COLUMNS = (
    "tourney_id,tourney_name,surface,draw_size,tourney_level,indoor,"
    "tourney_date,match_num,winner_id,winner_seed,winner_entry,winner_name,"
    "winner_hand,winner_ht,winner_ioc,winner_age,winner_rank,winner_rank_points,"
    "loser_id,loser_seed,loser_entry,loser_name,loser_hand,loser_ht,loser_ioc,"
    "loser_age,loser_rank,loser_rank_points,score,best_of,round,minutes,"
    "w_ace,w_df,w_svpt,w_1stIn,w_1stWon,w_2ndWon,w_SvGms,w_bpSaved,"
    "w_bpFaced,l_ace,l_df,l_svpt,l_1stIn,l_1stWon,l_2ndWon,l_SvGms,"
    "l_bpSaved,l_bpFaced"
).split(",")

EXPECTED_REGISTRY_VERSION = "TML_2024_FEB_SOURCE_METADATA_CROSSWALK_1"
MODE = "PERSONAL_NONCOMMERCIAL_RESEARCH"


def _digest(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    nbytes = 0
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                nbytes += len(chunk)
                digest.update(chunk)
    except OSError as exc:
        raise ValueError("TML source unreadable") from exc
    if nbytes == 0:
        raise ValueError("TML source is empty")
    return digest.hexdigest(), nbytes


def _crosswalk(crosswalk: dict, official: dict) -> list[dict]:
    if (not isinstance(crosswalk, dict)
            or crosswalk.get("registry_version") != EXPECTED_REGISTRY_VERSION
            or crosswalk.get("mode") != MODE
            or crosswalk.get("source_file") != "2024.csv"):
        raise ValueError("invalid research-only TML registry")
    if (not isinstance(official, dict) or official.get("calendar_version")
            != "P1_OFFICIAL_EVENT_CALENDAR_1"
            or not isinstance(official.get("events"), list)
            or not isinstance(crosswalk.get("entries"), list)):
        raise ValueError("invalid pinned official event calendar")
    by_key = {}
    for event in official["events"]:
        if not isinstance(event, dict) or not isinstance(event.get("event_key"), str):
            raise ValueError("invalid official event row")
        if event["event_key"] in by_key:
            raise ValueError("duplicate official event key")
        by_key[event["event_key"]] = event

    entries = crosswalk["entries"]
    if len(entries) != 12 or len(by_key) != 12:
        raise ValueError("TML audit requires exactly twelve official February 2024 events")
    keys = []
    ids = []
    for item in entries:
        if not isinstance(item, dict):
            raise ValueError("invalid TML tournament crosswalk row")
        key = item.get("official_event_key")
        src = item.get("source_tourney_id")
        if not isinstance(key, str) or not isinstance(src, str) or key not in by_key:
            raise ValueError("unrecognized TML or official event identity")
        official_event = by_key[key]
        if (item.get("official_tier") != official_event.get("official_tier")
                or item.get("tourney_date") != official_event.get("start_date", "").replace("-", "")
                or official_event.get("official_year") != 2024
                or not isinstance(item.get("expected_rounds"), dict)
                or type(item.get("observed_row_count")) is not int
                or sum(item["expected_rounds"].values()) != item["observed_row_count"]
                or item.get("surface") not in ("Hard", "Clay", "Grass")
                or not isinstance(item.get("source_tourney_name"), str)):
            raise ValueError("TML crosswalk conflicts with pinned ATP official calendar")
        keys.append(key)
        ids.append(src)
    if len(set(keys)) != 12 or len(set(ids)) != 12:
        raise ValueError("duplicated or missing TML/ATP event mapping")
    return entries


def audit_tml_february_2024(csv_path: Path, crosswalk: dict, official_calendar: dict) -> dict:
    """Check a local TML 2024 CSV and report *candidate* round/identity coverage.

    All reports remain blocked for model training and allocation until an
    independent official-draw match/round reconciliation and per-match date
    verification are performed. No live/retrospective odds here.
    """
    entries = _crosswalk(crosswalk, official_calendar)
    path = Path(csv_path)
    source_sha, size = _digest(path)
    if path.name != "2024.csv":
        match = re.fullmatch(r"2024-([a-f0-9]{64})\\.csv", path.name)
        if match is None or match.group(1) != source_sha:
            raise ValueError("TML versioned snapshot filename/content hash mismatch")
    ids = {entry["source_tourney_id"]: entry for entry in entries}
    grouped: dict[str, list[dict]] = defaultdict(list)
    raw_levels: dict[str, set[str]] = defaultdict(set)
    source_rows = 0
    anomalies: list[str] = []
    seen: set[tuple[str, str]] = set()

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, strict=True)
            if reader.fieldnames != TML_COLUMNS:
                raise ValueError("TML CSV schema drift or invalid 50-column header")
            for number, row in enumerate(reader, start=2):
                source_rows += 1
                if None in row or any(value is None for value in row.values()):
                    raise ValueError(f"TML CSV schema: corrupt row {number}")
                sid = row["tourney_id"]
                if sid not in ids:
                    continue
                entry = ids[sid]
                grouped[sid].append(row)
                raw_levels[sid].add(row["tourney_level"])
                match_key = (sid, row["match_num"])
                if not row["match_num"] or match_key in seen:
                    anomalies.append(f"DUPLICATE_MATCH:{sid}:{row['match_num']}")
                seen.add(match_key)
                if (not row["winner_id"] or not row["loser_id"]
                        or row["winner_id"] == row["loser_id"]
                        or not row["winner_name"] or not row["loser_name"]):
                    anomalies.append(f"PLAYER_IDENTITY:{sid}:{row['match_num']}")
                if (row["tourney_name"] != entry["source_tourney_name"]
                        or row["tourney_date"] != entry["tourney_date"]
                        or row["surface"] != entry["surface"]):
                    anomalies.append(f"TOURNAMENT_METADATA:{sid}:{row['match_num']}")
                if (row["best_of"] != "3" or row["draw_size"] != "32"
                        or row["tourney_level"] not in ("250", "500", "A")):
                    anomalies.append(f"TOURNAMENT_FORMAT:{sid}:{row['match_num']}")
                if not row["score"]:
                    anomalies.append(f"EMPTY_SCORE:{sid}:{row['match_num']}")
    except (OSError, UnicodeError, csv.Error) as exc:
        raise ValueError("TML CSV unreadable, malformed or invalid encoding") from exc

    events: list[dict] = []
    for item in entries:
        sid = item["source_tourney_id"]
        rows = grouped.get(sid, [])
        counts = dict(Counter(r["round"] for r in rows))
        if not rows:
            anomalies.append(f"MISSING_EVENT:{item['official_event_key']}")
        if len(rows) != item["observed_row_count"]:
            anomalies.append(f"ROW_COUNT_MISMATCH:{item['official_event_key']}")
        if counts != item["expected_rounds"]:
            anomalies.append(f"ROUND_HISTOGRAM:{item['official_event_key']}")
        events.append({
            "official_event_key": item["official_event_key"],
            "source_tourney_id": sid,
            "official_tier": item["official_tier"],
            "observed_rows": len(rows),
            "expected_rows": item["observed_row_count"],
            "observed_rounds": counts,
            "expected_rounds": item["expected_rounds"],
            "provider_levels": sorted(raw_levels.get(sid, set())),
            "tourney_date": item["tourney_date"],
        })

    anomalies = sorted(set(anomalies))
    return {
        "status": "SOURCE_CANDIDATE_INCONSISTENT" if anomalies else "SOURCE_CANDIDATE_REVIEW_REQUIRED",
        "mode": MODE,
        "source_file": path.name,
        "source_sha256": source_sha,
        "source_size_bytes": size,
        "source_rows": source_rows,
        "observed_target_matches": sum(len(v) for v in grouped.values()),
        "observed_target_events": sum(bool(grouped.get(e["source_tourney_id"])) for e in entries),
        "expected_target_events": len(entries),
        "source_date_semantics": "TOURNAMENT_START_DATE_NOT_MATCH_START",
        "source_match_id_semantics": "TOURNEY_ID_PLUS_MATCH_NUM_NOT_OFFICIAL_MATCH_ID",
        "events": events,
        "anomalies": anomalies,
        "source_personal_noncommercial_terms_url": crosswalk.get("provider_terms_url"),
        "source_rights_scope": "PERSONAL_NONCOMMERCIAL_RESEARCH_ONLY",
        "main_draw_verified": False,
        "individual_match_start_verified": False,
        "historical_match_outcomes_verified": False,
        "t60_quote_verified": False,
        "eligible_for_model_training": 0,
        "allocation_enabled": False,
        "stake": 0,
        "warnings": [
            "TOURNEY_DATE_IS_TOURNAMENT_WEEK_NOT_MATCH_DATE",
            "SOURCE_TIER_A_IS_AMBIGUOUS_OFFICIAL_TIER_CONTROLS",
            "OFFICIAL_MATCH_DRAW_AND_OUTCOMES_REQUIRE_SEPARATE_AUDIT",
            "NO_EXECUTABLE_T60_ODDS_OR_REAL_MONEY_ALLOCATION",
            "NO_RAW_CSV_REDISTRIBUTION",
        ],
    }
