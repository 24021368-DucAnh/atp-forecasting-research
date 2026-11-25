"""Read-only pinned TML source diagnostics; no official identity certification."""
from __future__ import annotations

import csv
import hashlib
import io
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from .tml_historical_audit import TML_COLUMNS

_FILENAME = re.compile(r"([0-9]{4})(?:-([a-f0-9]{64}))?\.csv")
_NUM = re.compile(r"[0-9]{1,12}")
_SHA = re.compile(r"[a-f0-9]{64}")
_ROUNDS = {r: i for i, r in enumerate(("R128", "R64", "R32", "R16", "QF", "SF", "F"))}
_LEVELS = {"250", "500", "M", "G"}
_REVIEWED_2024_SHA = "db27fb184b62bc1716ecc84c5a8365088e34e8e9a0101a59782ec7907f6e2de8"
_REVIEWED_2024 = {"2024-451", "2024-7480"}
_CAP = 20 * 1024 * 1024
_COUNT_KEYS = (
    "source_rows", "well_formed_rows", "malformed_rows", "missing_event_id_rows",
    "missing_match_num_rows", "invalid_match_num_rows", "noncanonical_match_num_rows",
    "duplicate_raw_match_key_groups", "duplicate_numeric_match_key_groups",
    "invalid_player_pair_rows", "missing_player_name_fields", "missing_round_rows",
    "duplicate_candidate_pair_round_groups", "conflicting_candidate_outcome_groups",
    "player_ids_with_multiple_name_tokens", "name_tokens_with_multiple_player_ids",
    "invalid_source_date_rows", "cross_year_start_rows", "one_day_date_variant_events",
    "date_spread_gt_one_day_events", "event_surface_variant_events",
    "knockout_candidate_events", "unsupported_knockout_format_events",
    "candidate_missing_final_events", "candidate_multiple_final_events",
    "candidate_loser_reappears_events", "candidate_disconnected_bracket_events",
)


def _token(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


def _bracket(rows: list[tuple[str, str, str]], counts: Counter) -> None:
    if any(r not in _ROUNDS for _, _, r in rows):
        counts["unsupported_knockout_format_events"] += 1
        return
    counts["knockout_candidate_events"] += 1
    finals = sum(r == "F" for _, _, r in rows)
    counts["candidate_missing_final_events"] += int(finals == 0)
    counts["candidate_multiple_final_events"] += int(finals > 1)
    edges: dict[str, set[str]] = defaultdict(set)
    latest: dict[str, int] = defaultdict(lambda: -1)
    for w, l, r in rows:
        edges[w].add(l)
        edges[l].add(w)
        latest[w] = max(latest[w], _ROUNDS[r])
        latest[l] = max(latest[l], _ROUNDS[r])
    if any(latest[l] > _ROUNDS[r] for _, l, r in rows):
        counts["candidate_loser_reappears_events"] += 1
    if edges:
        visited = set()
        pending = [next(iter(edges))]
        while pending:
            p = pending.pop()
            if p not in visited:
                visited.add(p)
                pending.extend(edges[p] - visited)
        counts["candidate_disconnected_bracket_events"] += int(len(visited) != len(edges))


def audit_tml_identity(paths, *, expected_sha256: dict[int, str]) -> dict:
    """Profile source-level defects without resolving ambiguous matches or players."""
    if (not isinstance(expected_sha256, dict) or not expected_sha256
            or any(type(y) is not int or not isinstance(v, str) or not _SHA.fullmatch(v)
                   for y, v in expected_sha256.items())):
        raise ValueError("exact season SHA256 pins required")
    counts = Counter({k: 0 for k in _COUNT_KEYS})
    raw_keys, numeric_keys, pair_keys = Counter(), Counter(), Counter()
    pair_winners, names_by_id, ids_by_name = defaultdict(set), defaultdict(set), defaultdict(set)
    pair_scopes = defaultdict(set)
    dates, surfaces = defaultdict(set), defaultdict(set)
    brackets = defaultdict(list)
    seen = set()
    inventory = []
    for raw_path in paths:
        path = Path(raw_path)
        filename = _FILENAME.fullmatch(path.name)
        if filename is None:
            raise ValueError("source requires YYYY or YYYY-SHA256 CSV filename")
        year = int(filename[1])
        if not 1968 <= year <= 2026 or year in seen:
            raise ValueError("invalid or duplicate source season")
        seen.add(year)
        with path.open("rb") as handle:
            data = handle.read(_CAP + 1)
        if not 0 < len(data) <= _CAP:
            raise ValueError("empty or oversized source")
        sha = hashlib.sha256(data).hexdigest()
        if expected_sha256.get(year) != sha or (filename[2] and filename[2] != sha):
            raise ValueError("source SHA256 pin mismatch")
        local = Counter()
        try:
            reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline=""), strict=True)
            if reader.fieldnames != TML_COLUMNS:
                raise ValueError("TML 50-column schema drift")
            for row in reader:
                local["source_rows"] += 1
                if None in row or any(v is None for v in row.values()):
                    local["malformed_rows"] += 1
                    continue
                local["well_formed_rows"] += 1
                event, num = row["tourney_id"], row["match_num"]
                if not event.strip():
                    local["missing_event_id_rows"] += 1
                if not num.strip():
                    local["missing_match_num_rows"] += 1
                else:
                    if event.strip():
                        raw_keys[event, num] += 1
                    if not _NUM.fullmatch(num) or int(num) <= 0:
                        local["invalid_match_num_rows"] += 1
                    else:
                        n = int(num)
                        if str(n) != num:
                            local["noncanonical_match_num_rows"] += 1
                        if event.strip():
                            numeric_keys[event, n] += 1
                raw_date = row["tourney_date"]
                try:
                    if not re.fullmatch(r"[0-9]{8}", raw_date):
                        raise ValueError("invalid date")
                    d = datetime.strptime(raw_date, "%Y%m%d").date()
                    if d.year != year:
                        if d.year != year - 1 or d.month != 12 or d.day < 25:
                            raise ValueError("outside source season")
                        local["cross_year_start_rows"] += 1
                    if event.strip():
                        dates[event].add(d)
                except ValueError:
                    local["invalid_source_date_rows"] += 1
                if event.strip():
                    surfaces[event].add(row["surface"])
                for role in ("winner", "loser"):
                    player, name = row[role + "_id"], _token(row[role + "_name"])
                    if not name:
                        local["missing_player_name_fields"] += 1
                    if player.strip() and name:
                        names_by_id[player].add(name)
                        ids_by_name[name].add(player)
                w, l, r = row["winner_id"], row["loser_id"], row["round"]
                if not r.strip():
                    local["missing_round_rows"] += 1
                if not w.strip() or not l.strip() or w == l:
                    local["invalid_player_pair_rows"] += 1
                    continue
                in_main_scope = (row["tourney_level"] in _LEVELS
                                 or (year == 2024 and sha == _REVIEWED_2024_SHA
                                     and event in _REVIEWED_2024))
                if event.strip() and r.strip():
                    k = (event, *sorted((w, l)), r)
                    pair_keys[k] += 1
                    pair_winners[k].add(w)
                    pair_scopes[k].add(in_main_scope)
                if event.strip() and in_main_scope:
                    brackets[event].append((w, l, r))
        except (UnicodeError, csv.Error) as exc:
            raise ValueError("invalid source encoding or CSV") from exc
        counts.update(local)
        inventory.append({"season": year, "sha256": sha, "size_bytes": len(data),
                          "counts": {k: local[k] for k in _COUNT_KEYS
                                     if k.endswith("_rows") or k == "missing_player_name_fields"}})
    if seen != set(expected_sha256):
        raise ValueError("source season set differs from SHA256 pin manifest")
    counts["duplicate_raw_match_key_groups"] = sum(v > 1 for v in raw_keys.values())
    counts["duplicate_numeric_match_key_groups"] = sum(v > 1 for v in numeric_keys.values())
    counts["duplicate_candidate_pair_round_groups"] = sum(v > 1 for v in pair_keys.values())
    counts["conflicting_candidate_outcome_groups"] = sum(len(v) > 1 for v in pair_winners.values())
    duplicate_scopes = Counter({"MAIN_TOUR": 0, "OUTSIDE_MAIN_TOUR": 0, "MIXED_SCOPE": 0})
    for key, n in pair_keys.items():
        if n > 1:
            scope = pair_scopes[key]
            bucket = ("MIXED_SCOPE" if len(scope) > 1 else
                      "MAIN_TOUR" if True in scope else "OUTSIDE_MAIN_TOUR")
            duplicate_scopes[bucket] += 1
    counts["player_ids_with_multiple_name_tokens"] = sum(len(v) > 1 for v in names_by_id.values())
    counts["name_tokens_with_multiple_player_ids"] = sum(len(v) > 1 for v in ids_by_name.values())
    counts["one_day_date_variant_events"] = sum((max(v) - min(v)).days == 1 for v in dates.values())
    counts["date_spread_gt_one_day_events"] = sum((max(v) - min(v)).days > 1 for v in dates.values())
    counts["event_surface_variant_events"] = sum(len(v) > 1 for v in surfaces.values())
    for rows in brackets.values():
        _bracket(rows, counts)
    return {
        "schema": "TML_PINNED_IDENTITY_AUDIT_V2",
        "status": "INTERNAL_SOURCE_DIAGNOSTICS_REVIEW_REQUIRED",
        "mode": "PERSONAL_NONCOMMERCIAL_RESEARCH",
        "source_inventory": sorted(inventory, key=lambda item: item["season"]),
        "counts": dict(counts),
        "duplicate_candidate_groups_by_scope": dict(duplicate_scopes),
        "source_date_semantics": "TOURNAMENT_START_NOT_INDIVIDUAL_MATCH_START",
        "knockout_scope": "MAIN_TOUR_LEVELS_PLUS_PINNED_2024_REVIEWED_EVENTS",
        "warnings": [
            "NAME_TOKENS_ARE_REVIEW_LEADS_NOT_PLAYER_ID_ALIASES",
            "INTERNAL_CONNECTIVITY_DOES_NOT_PROVE_OFFICIAL_DRAW_COMPLETENESS",
            "INVALID_PLAYER_PAIR_ROWS_EXCLUDED_FROM_GRAPH",
            "UNSUPPORTED_ROUNDS_NOT_TREATED_AS_KNOCKOUT",
            "SOURCE_ROWS_NOT_COMPLETED_MATCH_LABELS",
        ],
        "official_match_draw_verified": False,
        "source_independence_verified": False,
        "individual_match_start_verified": False,
        "eligible_for_model_training": 0,
        "model_validation_trusted": False,
        "allocation_enabled": False,
        "stake": 0,
    }
