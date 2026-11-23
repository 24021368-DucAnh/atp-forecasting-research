"""Read-only source coverage for accepted historical ATP research observations.

The loader remains the sole authority on eligibility and deduplication.
A profile is NOT approval to train, evidence of licensed usage, or T-60 odds.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Iterable

from .research_data import load_historical_matches


def _ordered_counts(counts: Counter) -> dict:
    return {str(k): int(v) for k, v in sorted(counts.items())}


def profile_historical_sources(
    paths: str | Path | Iterable[str | Path],
    *,
    expected_start_year: int | None = None,
    expected_end_year: int | None = None,
) -> dict:
    """Summarize accepted matches by observed season, tier, surface and source.

    Explicitly separate data quality from verified provenance/licensing.
    Both expected-year bounds must be given together, inclusively.
    """
    if isinstance(paths, (str, Path)):
        paths = [paths]
    sources = [Path(p) for p in paths]
    if not sources:
        raise ValueError("at least one historical source is required")

    names = [path.name for path in sources]
    if len({name.casefold() for name in names}) != len(names):
        raise ValueError("duplicate source basename: use distinct filenames to preserve source lineage")

    if (expected_start_year is None) != (expected_end_year is None):
        raise ValueError("expected year range requires both start and end")
    if expected_start_year is not None and (
        type(expected_start_year) is not int
        or type(expected_end_year) is not int
        or not 1900 <= expected_start_year <= expected_end_year <= 2100
    ):
        raise ValueError("expected year range must be inclusive, increasing, between 1900 and 2100")

    accepted, audit = load_historical_matches(sources)

    per_year: Counter = Counter()
    per_tier: Counter = Counter()
    per_surface: Counter = Counter()
    by_source: Counter = Counter({name: 0 for name in names})
    by_year_tier: dict[str, Counter] = {}
    by_year_quality: dict[str, dict[str, int]] = {}

    missing_odds = 0
    missing_rank = 0
    player_names: set[str] = set()
    for match in accepted:
        year = str(match.day.year)
        per_year[year] += 1
        per_tier[match.tier] += 1
        per_surface[match.surface] += 1
        source_name = match.source_row.split(":", 1)[0]
        by_source[source_name] += 1
        by_year_tier.setdefault(year, Counter())[match.tier] += 1
        player_names.update((match.player_a, match.player_b))

        missing_o = int(match.odds_a is None or match.odds_b is None)
        missing_r = int(match.rank_a is None or match.rank_b is None)
        missing_odds += missing_o
        missing_rank += missing_r
        quality_row = by_year_quality.setdefault(
            year, {"accepted": 0, "missing_odds": 0, "missing_rank": 0}
        )
        quality_row["accepted"] += 1
        quality_row["missing_odds"] += missing_o
        quality_row["missing_rank"] += missing_r

    observed_years = sorted(int(year) for year in per_year)
    expected_years = (
        list(range(expected_start_year, expected_end_year + 1))
        if expected_start_year is not None else []
    )
    missing_expected = sorted(set(expected_years) - set(observed_years))
    sources_without_matches = sorted(name for name, n in by_source.items() if n == 0)

    warnings = [
        "SOURCE_LICENSE_UNVERIFIED",
        "PLAYER_IDENTITY_UNVERIFIED",
        "HISTORICAL_DAY_ONLY_NO_T60",
    ]
    if audit["duplicate"]:
        warnings.append("DUPLICATES_SKIPPED")
    if missing_odds:
        warnings.append("MISSING_ODDS")
    if missing_rank:
        warnings.append("MISSING_RANK")
    if missing_expected:
        warnings.append("EXPECTED_YEAR_MISSING")
    if sources_without_matches:
        warnings.append("SOURCE_WITHOUT_ACCEPTED_ROWS")
    if not accepted:
        warnings.append("NO_ACCEPTED_MATCHES")

    count = len(accepted)
    incomplete = not accepted or bool(missing_expected) or bool(sources_without_matches)
    return {
        "status": "INCOMPLETE" if incomplete else "PROFILED",
        "mode": "HISTORICAL_RESEARCH_ONLY",
        "profile_version": "P1_SOURCE_PROFILE_1",
        "source_audit": audit,
        "coverage": {
            "accepted_matches": count,
            "observed_years": observed_years,
            "expected_years": expected_years,
            "missing_expected_years": missing_expected,
            "first_match_date": str(accepted[0].day) if accepted else None,
            "last_match_date": str(accepted[-1].day) if accepted else None,
            "by_year": _ordered_counts(per_year),
            "by_tier": _ordered_counts(per_tier),
            "by_surface": _ordered_counts(per_surface),
            "by_year_tier": {yr: _ordered_counts(tiers)
                             for yr, tiers in sorted(by_year_tier.items())},
            "by_source": _ordered_counts(by_source),
            "source_without_accepted_matches": sources_without_matches,
            "unique_player_name_strings": len(player_names),
        },
        "quality": {
            "missing_odds": missing_odds,
            "missing_rank": missing_rank,
            "missing_odds_ratio": round(missing_odds / count, 6) if count else None,
            "missing_rank_ratio": round(missing_rank / count, 6) if count else None,
            "by_year": {yr: dict(values) for yr, values in sorted(by_year_quality.items())},
        },
        "warnings": warnings,
        "source_identity_verified": False,
        "source_license_verified": False,
        "live_eligible": False,
        "allocation_enabled": False,
        "validation_report_trusted": False,
        "stake": 0,
    }
