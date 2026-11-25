"""Research-only TML/Sackmann archive comparison of Feb 2024 match identities.

This is a cross-PUBLICATION provenance check, NOT independent official ATP
result certification. Neither provider's player IDs or match numbers may be
joined directly; both datasets can share Jeff Sackmann historical lineage.
"""
from __future__ import annotations

import csv
import hashlib
import io
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from .tml_historical_audit import TML_COLUMNS

ARCHIVE_COLUMNS = (
    "tourney_id,tourney_name,surface,draw_size,tourney_level,tourney_date,"
    "match_num,winner_id,winner_seed,winner_entry,winner_name,winner_hand,"
    "winner_ht,winner_ioc,winner_age,loser_id,loser_seed,loser_entry,"
    "loser_name,loser_hand,loser_ht,loser_ioc,loser_age,score,best_of,round,"
    "minutes,w_ace,w_df,w_svpt,w_1stIn,w_1stWon,w_2ndWon,w_SvGms,"
    "w_bpSaved,w_bpFaced,l_ace,l_df,l_svpt,l_1stIn,l_1stWon,l_2ndWon,"
    "l_SvGms,l_bpSaved,l_bpFaced,winner_rank,winner_rank_points,"
    "loser_rank,loser_rank_points"
).split(",")
MAX_FILE_BYTES = 20 * 1024 * 1024
MODE = "PERSONAL_NONCOMMERCIAL_RESEARCH"


def _norm_name(name: str) -> str:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("missing player display name")
    ascii_form = unicodedata.normalize("NFKD", name)
    ascii_form = "".join(ch for ch in ascii_form if not unicodedata.combining(ch))
    token = re.sub(r"[^a-z0-9]", "", ascii_form.lower())
    if not token:
        raise ValueError("unusable player display name")
    return token


def _event_id(raw: str) -> str:
    if not isinstance(raw, str):
        raise ValueError("invalid provider event ID")
    found = re.fullmatch(r"(\d{4})-(\d+)", raw)
    if found:
        return f"{found.group(1)}-{int(found.group(2))}"
    return raw


def _read(path: Path, columns: list[str]) -> tuple[str, list[dict]]:
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        raise ValueError("archive/partner source file unreadable") from exc
    if not 0 < len(data) <= MAX_FILE_BYTES:
        raise ValueError("invalid source file size")
    digest = hashlib.sha256(data).hexdigest()
    try:
        text = data.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
        if reader.fieldnames != columns:
            raise ValueError("cross-publication source schema drift")
        rows = []
        for row in reader:
            if None in row or any(x is None for x in row.values()):
                raise ValueError("cross-publication source schema malformed row")
            rows.append(row)
    except (UnicodeError, csv.Error) as exc:
        raise ValueError("cross-publication source encoding/CSV malformed") from exc
    return digest, rows


def _validate_aliases(aliases: dict) -> dict[str, str]:
    if (not isinstance(aliases, dict)
            or aliases.get("version") != "TML_SACKMANN_ALIAS_2024_1"
            or aliases.get("scope") != "2024_FEB_ATP"
            or not isinstance(aliases.get("mapping"), dict)):
        raise ValueError("invalid or unreviewed player alias registry version")
    normalized: dict[str, str] = {}
    reverse: dict[str, str] = {}
    for source, target in aliases["mapping"].items():
        src, dest = _norm_name(source), _norm_name(target)
        if src in normalized or (dest in reverse and reverse[dest] != src):
            raise ValueError("ambiguous cross-provider name alias mapping")
        if src == dest:
            raise ValueError("redundant cross-provider alias")
        normalized[src] = dest
        reverse[dest] = src
    return normalized


def audit_tml_sackmann_crosspublication(
    tml_path: Path, archive_path: Path, crosswalk: dict, aliases: dict,
) -> dict:
    """Compare exact historical identity/round/score on all 12 mapped events.

    Score-string differences are retained as audit findings, never silently
    converted into a completed result. No raw match records in output.
    """
    if (not isinstance(crosswalk, dict)
            or crosswalk.get("registry_version") != "TML_2024_FEB_SOURCE_METADATA_CROSSWALK_1"
            or crosswalk.get("mode") != MODE
            or not isinstance(crosswalk.get("entries"), list)
            or len(crosswalk["entries"]) != 12):
        raise ValueError("invalid TML February event crosswalk")
    keyed = {}
    source_ids = set()
    expected = 0
    for e in crosswalk["entries"]:
        if not isinstance(e, dict):
            raise ValueError("invalid event registry entry")
        key = e.get("source_tourney_id")
        event = e.get("official_event_key")
        size = e.get("observed_row_count")
        if (not isinstance(key, str) or not isinstance(event, str)
                or type(size) is not int or size <= 0
                or _event_id(key) in keyed or event in source_ids):
            raise ValueError("duplicate or invalid event registry mapping")
        keyed[_event_id(key)] = e
        source_ids.add(event)
        expected += size
    map_names = _validate_aliases(aliases)
    if Path(tml_path).resolve() == Path(archive_path).resolve():
        raise ValueError("source files must be separate")
    t_sha, t_rows = _read(Path(tml_path), TML_COLUMNS)
    s_sha, s_rows = _read(Path(archive_path), ARCHIVE_COLUMNS)
    targets: dict[str, dict[str, dict]] = defaultdict(dict)
    ref: dict[str, dict[str, dict]] = defaultdict(dict)
    for rows, dest, use_alias in ((t_rows, targets, True), (s_rows, ref, False)):
        for row in rows:
            sid = _event_id(row["tourney_id"])
            event = keyed.get(sid)
            if event is None:
                continue
            if row["tourney_date"] != event["tourney_date"]:
                raise ValueError("cross-publication tournament-start date conflicts with registry")
            round_name = row["round"]
            if not round_name or round_name not in event["expected_rounds"]:
                raise ValueError("cross-publication unknown round code")
            w = _norm_name(row["winner_name"])
            l = _norm_name(row["loser_name"])
            if use_alias:
                w = map_names.get(w, w)
                l = map_names.get(l, l)
            if w == l:
                raise ValueError("player identity collapsed by alias")
            key = w + "|" + l + "|" + round_name
            if key in dest[sid]:
                raise ValueError("duplicate/ambiguous player-round identity in source")
            dest[sid][key] = row

    details = []
    matched_all = 0
    scores_same = 0
    score_diffs = 0
    t_n = 0
    a_n = 0
    fully_aligned = True
    for item in crosswalk["entries"]:
        sid = _event_id(item["source_tourney_id"])
        t, a = targets.get(sid, {}), ref.get(sid, {})
        commons = set(t).intersection(a)
        score_eq = sum(t[k]["score"].strip() == a[k]["score"].strip() for k in commons)
        mismatch = len(commons) - score_eq
        if len(t) != item["observed_row_count"] or len(a) != item["observed_row_count"] or len(commons) != item["observed_row_count"]:
            fully_aligned = False
        matched_all += len(commons)
        scores_same += score_eq
        score_diffs += mismatch
        t_n += len(t)
        a_n += len(a)
        details.append({
            "official_event_key": item["official_event_key"],
            "tml_rows": len(t),
            "archive_rows": len(a),
            "matched_player_names_and_round": len(commons),
            "exact_score_text_matches": score_eq,
            "score_text_differences": mismatch,
            "unmatched_tml": len(t) - len(commons),
            "unmatched_archive": len(a) - len(commons),
        })
    return {
        "status": ("CROSS_PUBLICATION_AGREEMENT_REVIEW_REQUIRED" if fully_aligned
                   else "CROSS_PUBLICATION_CONFLICT_REVIEW_REQUIRED"),
        "mode": MODE,
        "tml_source_sha256": t_sha,
        "archive_source_sha256": s_sha,
        "target_tml_rows": t_n,
        "target_archive_rows": a_n,
        "expected_target_rows": expected,
        "matched_player_names_and_round": matched_all,
        "exact_score_text_matches": scores_same,
        "score_text_differences": score_diffs,
        "events": details,
        "name_aliases_explicitly_curated": len(map_names),
        "event_id_numeric_padding_normalized": True,
        "different_player_id_namespaces": True,
        "source_independence_verified": False,
        "official_match_draw_verified": False,
        "individual_match_start_verified": False,
        "t60_quote_verified": False,
        "eligible_for_model_training": 0,
        "allocation_enabled": False,
        "stake": 0,
        "warnings": [
            "PROVIDERS_MAY_SHARE_JEFF_SACKMANN_SOURCE_LINEAGE",
            "PLAYER_NAMES_REQUIRE_APPROVED_ALIAS_MAP_NOT_FUZZY_JOINS",
            "MATCH_NUMBERS_AND_PLAYER_IDS_NOT_CROSS_PROVIDER_KEYS",
            "RETIREMENT_SCORE_TEXT_MUST_NOT_BE_TREATED_AS_COMPLETED_SET",
            "PUBLIC_MATCH_SOURCE_NOT_INDEPENDENT_OFFICIAL_ATP_DRAW",
            "NO_T60_QUOTES_OR_REAL_MONEY_ALLOCATION",
        ],
    }
