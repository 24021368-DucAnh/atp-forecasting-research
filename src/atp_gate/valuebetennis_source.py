"""Read-only inspection of Valuebetennis annual CSVs. Not a model adapter.

Valuebetennis publishes semicolon-separated ATP/WTA singles results under
CC BY 4.0: https://www.valuebetennis.com/en/donnees.htm

Main tour != ATP500; numeric 'tour' is a round, not the circuit; opening
and closing odds are not authenticated T-60 quotes. Never enable training
or allocation from this inventory.
"""
from __future__ import annotations

import csv
import hashlib
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

_REQUIRED = {
    "match_id", "date", "tournoi", "tournoi_id", "categorie", "genre",
    "surface", "tour", "joueur1", "joueur1_id", "joueur2", "joueur2_id",
    "vainqueur_id", "cote1_ouverture", "cote2_ouverture",
    "cote1_cloture", "cote2_cloture",
}
_CATEGORIES = {
    "main tour": "Main tour",
    "masters": "Masters",
    "grand slam": "Grand Slam",
    "grand chelem": "Grand Slam",
}


def _positive_id(value: object) -> str | None:
    raw = str(value or "").strip()
    return raw if raw.isascii() and raw.isdecimal() and int(raw) > 0 else None


def _utc(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw or ":" not in raw or not ("T" in raw or " " in raw):
        # A bare calendar date is NOT a match timestamp.
        return None
    try:
        candidate = datetime.fromisoformat(raw[:-1] + "+00:00" if raw.endswith("Z") else raw)
        if candidate.tzinfo is None:
            # Contract source date is UTC, but not verified actual first serve.
            candidate = candidate.replace(tzinfo=timezone.utc)
        return candidate.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return None


def _valid_odds(left: object, right: object) -> bool:
    try:
        a = float(str(left or "").strip().replace(",", "."))
        b = float(str(right or "").strip().replace(",", "."))
    except (ValueError, TypeError):
        return False
    # Decimal odds in realistic finite range; no inference from bad quotes.
    return 1.0 < a < 1000.0 and 1.0 < b < 1000.0


def _sha256_and_length(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    length = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
            length += len(chunk)
    return digest.hexdigest(), length


def inspect_valuebetennis_sources(
    paths: str | Path | Iterable[str | Path],
    *,
    expected_start_year: int | None = None,
    expected_end_year: int | None = None,
) -> dict:
    """Count only valid ATP *candidates*; never resolve tier or main draw."""
    if isinstance(paths, (str, Path)):
        paths = [paths]
    sources = [Path(source) for source in paths]
    if not sources:
        raise ValueError("at least one local Valuebetennis CSV is required")
    basenames = [p.name for p in sources]
    if len({name.casefold() for name in basenames}) != len(basenames):
        raise ValueError("duplicate source basename: files need unambiguous names")
    if (expected_start_year is None) != (expected_end_year is None):
        raise ValueError("expected year range needs both start and end")
    if expected_start_year is not None and (
        type(expected_start_year) is not int
        or type(expected_end_year) is not int
        or not 1900 <= expected_start_year <= expected_end_year <= 2100
    ):
        raise ValueError("expected year bounds must be increasing and between 1900 and 2100")

    counts: Counter = Counter()
    by_year: Counter = Counter()
    by_category: Counter = Counter()
    by_surface: Counter = Counter()
    by_source: Counter = Counter({name: 0 for name in basenames})
    ids_to_names = defaultdict(set)
    names_to_ids = defaultdict(set)
    seen_match_ids: set[str] = set()
    manifest = []
    earliest: datetime | None = None
    latest: datetime | None = None
    missing_open = 0
    missing_close = 0

    for source in sources:
        if source.suffix.lower() != ".csv":
            raise ValueError("Valuebetennis inputs must be .csv")
        digest, size = _sha256_and_length(source)
        manifest.append({"name": source.name, "sha256": digest, "size_bytes": size})

        with source.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream, delimiter=";")
            if reader.fieldnames is None or not _REQUIRED.issubset(reader.fieldnames):
                absent = sorted(_REQUIRED.difference(reader.fieldnames or []))
                raise ValueError(f"missing columns in {source.name}: {absent}")
            for row in reader:
                counts["total_rows"] += 1
                if None in row:
                    counts["malformed_row"] += 1
                    continue
                genre = str(row["genre"] or "").strip().casefold()
                if genre != "atp":
                    counts["excluded_wta" if genre == "wta" else "excluded_other_genre"] += 1
                    continue
                category = _CATEGORIES.get(str(row["categorie"] or "").strip().casefold())
                if category is None:
                    counts["excluded_other_category"] += 1
                    continue
                match_id = _positive_id(row["match_id"])
                id_a = _positive_id(row["joueur1_id"])
                id_b = _positive_id(row["joueur2_id"])
                if not match_id or not id_a or not id_b or id_a == id_b:
                    counts["invalid_identity"] += 1
                    continue
                winner = _positive_id(row["vainqueur_id"])
                if winner not in (id_a, id_b):
                    counts["invalid_winner"] += 1
                    continue
                try:
                    round_index = int(str(row["tour"] or "").strip())
                    if str(round_index) != str(row["tour"] or "").strip() or not 0 <= round_index <= 12:
                        raise ValueError
                except ValueError:
                    counts["invalid_round"] += 1
                    continue
                match_time = _utc(row["date"])
                if match_time is None:
                    counts["invalid_date"] += 1
                    continue
                name_a = str(row["joueur1"] or "").strip()
                name_b = str(row["joueur2"] or "").strip()
                if not name_a or not name_b:
                    counts["invalid_identity"] += 1
                    continue
                if match_id in seen_match_ids:
                    counts["duplicate_match_id"] += 1
                    continue
                seen_match_ids.add(match_id)

                counts["atp_candidate_matches"] += 1
                year = str(match_time.year)
                by_year[year] += 1
                by_category[category] += 1
                by_surface[str(row["surface"] or "").strip() or "UNKNOWN"] += 1
                by_source[source.name] += 1
                ids_to_names[id_a].add(name_a)
                ids_to_names[id_b].add(name_b)
                names_to_ids[name_a.casefold()].add(id_a)
                names_to_ids[name_b.casefold()].add(id_b)
                if not _valid_odds(row["cote1_ouverture"], row["cote2_ouverture"]):
                    missing_open += 1
                if not _valid_odds(row["cote1_cloture"], row["cote2_cloture"]):
                    missing_close += 1
                earliest = min(earliest, match_time) if earliest else match_time
                latest = max(latest, match_time) if latest else match_time

    observed = sorted(int(year) for year in by_year)
    expected = (
        list(range(expected_start_year, expected_end_year + 1))
        if expected_start_year is not None else []
    )
    missing = sorted(set(expected) - set(observed))
    has_rows = bool(counts["atp_candidate_matches"])
    warnings = [
        "TOURNAMENT_TIER_UNMAPPED",
        "MAIN_DRAW_ROUNDS_UNVERIFIED",
        "OPENING_CLOSING_NOT_T60",
        "PROVIDER_DECLARED_UTC_NOT_VERIFIED_ACTUAL_START",
        "SOURCE_FILE_ORIGIN_NOT_AUTHENTICATED",
    ]
    if missing:
        warnings.append("EXPECTED_SEASONS_MISSING")
    if counts["duplicate_match_id"]:
        warnings.append("DUPLICATE_MATCH_IDS_EXCLUDED")
    if not has_rows:
        warnings.append("NO_ATP_TOUR_CANDIDATES")
    if missing_open:
        warnings.append("MISSING_OPENING_PRICE_PAIR")
    if missing_close:
        warnings.append("MISSING_CLOSING_PRICE_PAIR")

    return {
        "status": "INCOMPLETE" if not has_rows or missing else "INSPECTED_UNMAPPED",
        "mode": "HISTORICAL_RESEARCH_ONLY",
        "profile_version": "P1_VALUEBETENNIS_1",
        "provider_attribution": (
            "Valuebetennis, Tennis results and odds since 2021, "
            "https://www.valuebetennis.com/en/donnees.htm"
        ),
        "provider_declared_license": "CC BY 4.0",
        "source_files": manifest,
        "counts": {
            key: int(counts[key])
            for key in (
                "total_rows", "atp_candidate_matches", "excluded_wta",
                "excluded_other_genre",
                "excluded_other_category", "malformed_row", "invalid_identity",
                "invalid_winner", "invalid_round", "invalid_date",
                "duplicate_match_id",
            )
        },
        "coverage": {
            "observed_years": observed,
            "expected_years": expected,
            "missing_expected_years": missing,
            "first_observed_utc": earliest.isoformat() if earliest else None,
            "last_observed_utc": latest.isoformat() if latest else None,
            "by_year": dict(sorted(by_year.items())),
            "by_category": dict(sorted(by_category.items())),
            "by_surface": dict(sorted(by_surface.items())),
            "by_source": dict(sorted(by_source.items())),
            "unique_player_ids": len(ids_to_names),
        },
        "identity_quality": {
            "ids_with_multiple_display_names": sum(len(v) > 1 for v in ids_to_names.values()),
            "display_names_with_multiple_ids": sum(len(v) > 1 for v in names_to_ids.values()),
        },
        "price_quality": {
            "missing_opening_pair": missing_open,
            "missing_closing_pair": missing_close,
        },
        "warnings": warnings,
        "source_file_origin_verified": False,
        "identity_mapping_verified": False,
        "tier_mapping_verified": False,
        "main_draw_verified": False,
        "t60_quote_verified": False,
        "eligible_for_model_training": 0,
        "live_eligible": False,
        "allocation_enabled": False,
        "validation_report_trusted": False,
        "stake": 0,
    }
