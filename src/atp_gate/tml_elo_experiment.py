"""Source-pinned pre-tournament Elo SKILL study for personal ATP research only.

TML tourney_date is an event START date, not a match date. We score
retrospectively observed matchups with ratings frozen before each tournament
and embargo all outcomes for 28 days. Nothing here certifies an executable
prematch pairing, real-time quote, profitable bet, or model release.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import random
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Sequence

from .tml_historical_audit import TML_COLUMNS

_ALLOWED_LEVELS = frozenset({"250", "500", "M", "G"})
_ALLOWED_SURFACES = frozenset({"Hard", "Clay", "Grass"})
_BAD_SCORES = re.compile(r"\b(?:RET|W/O|WO|WALKOVER|DEF|DEFAULT|ABN|ABD|ABANDONED|CANCELLED|UNFINISHED|IN\s+PROGRESS)\b", re.I)
_FILENAME = re.compile(r"^(\d{4})(?:-([0-9a-f]{64}))?\.csv$")
_SOURCE_CAP = 20 * 1024 * 1024

# Versioned, code-owned subset of the reviewed edition inventory. Do not
# accept caller-supplied mapping files or infer a tier from raw code A.
_LEVEL_A_2024_SHA256 = "db27fb184b62bc1716ecc84c5a8365088e34e8e9a0101a59782ec7907f6e2de8"
_LEVEL_A_2024_EVENTS = (
    ("2024-451", "Doha", "20240219", "Hard", 27,
     "https://www.atptour.com/en/news/mensik-khachanov-doha-2024-final"),
    ("2024-7480", "Los Cabos", "20240219", "Hard", 27,
     "https://www.atptour.com/en/news/thompson-first-time-winner-spotlight-los-cabos-2024"),
)


def _level_a_registry() -> dict:
    return {
        "schema": "TML_LEVEL_A_2024_NORMALIZATION_V1",
        "source_season": 2024,
        "source_sha256": _LEVEL_A_2024_SHA256,
        "entries": [
            {"event_id": tid, "event_name": name, "start": start,
             "surface": surface, "source_level": "A", "canonical_level": "250",
             "expected_raw_rows": n, "official_metadata_reference": url}
            for tid, name, start, surface, n, url in _LEVEL_A_2024_EVENTS
        ],
    }


@dataclass(frozen=True)
class _Match:
    event_id: str
    start: date
    surface: str
    player_a: str
    player_b: str
    outcome_a: int


def orient_result(winner_id: str, loser_id: str) -> tuple[str, str, int]:
    """Choose A/B independently of the winner-first source column."""
    if not isinstance(winner_id, str) or not isinstance(loser_id, str):
        raise ValueError("invalid player identity pair")
    winner_id, loser_id = winner_id.strip(), loser_id.strip()
    if not winner_id or not loser_id or winner_id == loser_id:
        raise ValueError("invalid player identity pair")
    a, b = sorted((winner_id, loser_id))
    return a, b, int(winner_id == a)


# Conservative standard main-tour set token validation; not proof of
# official completion or winner correctness. Historical extended advantage
# sets and 13-12 final-set tie breaks are retained.
_SET_SCORE = re.compile(r"([0-9]{1,2})-([0-9]{1,2})(?:\([0-9]{1,2}\))?")


def _completed_score(score: str) -> bool:
    if not isinstance(score, str) or not score.strip() or _BAD_SCORES.search(score):
        return False
    for token in score.split():
        match = _SET_SCORE.fullmatch(token)
        if match is None:
            return False
        hi, lo = sorted(map(int, match.groups()), reverse=True)
        if not ((hi == 6 and lo <= 4) or (hi >= 7 and hi - lo == 2)
                or (hi, lo) in {(7, 6), (13, 12)}):
            return False
    return True


def _source_date(raw: str, season: int) -> date:
    if not isinstance(raw, str) or len(raw) != 8 or not raw.isdigit():
        raise ValueError("invalid TML tournament start date")
    try:
        d = datetime.strptime(raw, "%Y%m%d").date()
    except ValueError as exc:
        raise ValueError("invalid TML tournament start date") from exc
    if not (d.year == season or (
        d.year == season - 1 and d.month == 12 and d.day >= 25
    )):
        raise ValueError("TML tournament start date outside source season")
    return d


def _load(paths: Sequence[Path], *, normalize_level_a_2024: bool = False
          ) -> tuple[list[_Match], list[dict], Counter, int, dict | None]:
    if not isinstance(paths, (list, tuple)) or len(paths) < 4:
        raise ValueError("four or more local source seasons required")
    inventory: list[dict] = []
    events: list[_Match] = []
    excluded: Counter = Counter()
    seen_seasons: set[int] = set()
    seen_match_keys: set[tuple[str, str]] = set()
    event_dates: dict[str, set[date]] = defaultdict(set)
    event_surfaces: dict[str, str] = {}
    registry = _level_a_registry() if normalize_level_a_2024 else None
    reviewed = {e["event_id"]: e for e in registry["entries"]} if registry else {}
    normalized_raw: Counter = Counter()
    normalized_eligible: Counter = Counter()

    for raw_path in paths:
        path = Path(raw_path)
        match = _FILENAME.fullmatch(path.name)
        if not match:
            raise ValueError("TML source file needs YYYY.csv or YYYY-<sha256>.csv")
        season = int(match.group(1))
        if season in seen_seasons:
            raise ValueError("duplicate TML source season")
        seen_seasons.add(season)
        if not 1968 <= season <= 2026:
            raise ValueError("invalid or future TML source season")
        try:
            payload = path.read_bytes()
        except OSError as exc:
            raise ValueError("TML research source unreadable") from exc
        if not 0 < len(payload) <= _SOURCE_CAP:
            raise ValueError("TML research source empty or exceeds size cap")
        sha = hashlib.sha256(payload).hexdigest()
        if match.group(2) and match.group(2) != sha:
            raise ValueError("TML research source SHA filename mismatches bytes")
        if registry and season == 2024 and sha != registry["source_sha256"]:
            raise ValueError("level-A normalization source SHA256 does not match reviewed pin")
        try:
            from io import StringIO
            reader = csv.DictReader(
                StringIO(payload.decode("utf-8-sig"), newline=""), strict=True
            )
            if reader.fieldnames != TML_COLUMNS:
                raise ValueError("unexpected TML 50-column source schema")
            count = 0
            for row in reader:
                count += 1
                if None in row or any(value is None for value in row.values()):
                    excluded["MALFORMED_ROWS"] += 1
                    continue
                tid, mid = row["tourney_id"], row["match_num"]
                entry = reviewed.get(tid)
                level = row["tourney_level"]
                if entry is not None:
                    if (season != 2024 or row["tourney_name"] != entry["event_name"]
                            or row["tourney_date"] != entry["start"]
                            or row["surface"] != entry["surface"]
                            or level != entry["source_level"]):
                        raise ValueError("level-A normalization metadata mismatch")
                    normalized_raw[tid] += 1
                    level = entry["canonical_level"]
                if not tid or not mid:
                    # TML's historical 2025 public snapshot includes many
                    # matches with blank match_num. No guessed canonical ID.
                    excluded["MISSING_MATCH_ID"] += 1
                    continue
                key = (tid, mid)
                if key in seen_match_keys:
                    raise ValueError("duplicate TML tournament/match identity")
                seen_match_keys.add(key)
                start = _source_date(row["tourney_date"], season)
                surface = row["surface"]
                if level not in _ALLOWED_LEVELS:
                    excluded["OUT_OF_SCOPE_LEVEL"] += 1
                    continue
                if surface not in _ALLOWED_SURFACES:
                    excluded["UNKNOWN_SURFACE"] += 1
                    continue
                if tid in event_surfaces and event_surfaces[tid] != surface:
                    raise ValueError("conflicting TML tournament surface")
                event_surfaces[tid] = surface
                event_dates[tid].add(start)
                score = row["score"]
                if not _completed_score(score):
                    excluded["NON_COMPLETED"] += 1
                    continue
                try:
                    a, b, y = orient_result(row["winner_id"], row["loser_id"])
                except ValueError:
                    excluded["INVALID_PLAYER_ID"] += 1
                    continue
                events.append(_Match(tid, start, surface, a, b, y))
                if entry is not None:
                    normalized_eligible[tid] += 1
            inventory.append({
                "season": season,
                "source_file": path.name,
                "sha256": sha,
                "size_bytes": len(payload),
                "source_rows": count,
                "nominal_publisher_url": f"https://stats.tennismylife.org/data/{season}.csv",
                "actual_fetch_uri": None,
                "acquisition_mode": "LOCAL_INPUT_UNATTESTED",
            })
        except (UnicodeError, csv.Error) as exc:
            raise ValueError("invalid TML source UTF-8/CSV encoding") from exc

    audit = None
    if registry is not None:
        if 2024 not in seen_seasons:
            raise ValueError("level-A normalization requires pinned 2024 source")
        for tid, entry in reviewed.items():
            if normalized_raw[tid] != entry["expected_raw_rows"]:
                raise ValueError("level-A normalization event raw row count mismatch")
        registry_bytes = json.dumps(registry, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=True).encode("utf-8")
        audit = {
            "registry_schema": registry["schema"],
            "registry_sha256": hashlib.sha256(registry_bytes).hexdigest(),
            "source_sha256": registry["source_sha256"],
            "raw_rows": sum(normalized_raw.values()),
            "eligible_rows": sum(normalized_eligible.values()),
            "events": [
                {**entry, "raw_rows": normalized_raw[tid],
                 "eligible_rows": normalized_eligible[tid]}
                for tid, entry in reviewed.items()
            ],
            "official_match_draw_verified": False,
        }

    if not events:
        raise ValueError("no eligible completed tour-level TML matches")
    earliest: dict[str, date] = {}
    event_date_variants = 0
    for tid, dates in event_dates.items():
        if max(dates) - min(dates) > timedelta(days=1):
            raise ValueError("same TML tournament has unsafe start date spread")
        if len(dates) > 1:
            event_date_variants += 1
        earliest[tid] = min(dates)
    # The public 2024 archive contains three events with a one-day date
    # variation. Freeze every match in that tournament at its EARLIEST
    # observed date; never split it into sequential result-updating events.
    normalized = [replace(m, start=earliest[m.event_id]) for m in events]
    return normalized, sorted(inventory, key=lambda x: x["season"]), excluded, event_date_variants, audit


def _elo_p(rating_a: float, rating_b: float) -> float:
    # Differences under 3000 are expected; a numerical clip keeps exp stable.
    z = max(-15., min(15., (rating_a - rating_b) / 400.))
    p = 1. / (1. + 10. ** (-z))
    return min(1. - 1e-12, max(1e-12, p))


class _Ratings:
    def __init__(self) -> None:
        self.overall: dict[str, float] = {}
        self.surface: dict[tuple[str, str], float] = {}
        self.surface_n: Counter = Counter()

    def probabilities(self, m: _Match) -> tuple[float, float]:
        a = self.overall.get(m.player_a, 1500.)
        b = self.overall.get(m.player_b, 1500.)
        g = _elo_p(a, b)
        ka = (m.player_a, m.surface)
        kb = (m.player_b, m.surface)
        wa = self.surface_n[ka] / (self.surface_n[ka] + 20.)
        wb = self.surface_n[kb] / (self.surface_n[kb] + 20.)
        ra = a + .35 * wa * (self.surface.get(ka, 1500.) - 1500.)
        rb = b + .35 * wb * (self.surface.get(kb, 1500.) - 1500.)
        return g, _elo_p(ra, rb)

    def update_matured_date(self, matches: list[_Match]) -> None:
        """Apply all results in an event-start batch from unchanged priors."""
        global_delta: dict[str, float] = defaultdict(float)
        surface_delta: dict[tuple[str, str], float] = defaultdict(float)
        surface_counts: Counter = Counter()
        for m in matches:
            a, b = m.player_a, m.player_b
            p = _elo_p(self.overall.get(a, 1500.),
                       self.overall.get(b, 1500.))
            step = 24. * (m.outcome_a - p)
            global_delta[a] += step
            global_delta[b] -= step
            ka, kb = (a, m.surface), (b, m.surface)
            sp = _elo_p(self.surface.get(ka, 1500.),
                        self.surface.get(kb, 1500.))
            sstep = 24. * (m.outcome_a - sp)
            surface_delta[ka] += sstep
            surface_delta[kb] -= sstep
            surface_counts[ka] += 1
            surface_counts[kb] += 1
        for player, delta in global_delta.items():
            self.overall[player] = self.overall.get(player, 1500.) + delta
        for player_surface, delta in surface_delta.items():
            self.surface[player_surface] = self.surface.get(player_surface, 1500.) + delta
        self.surface_n.update(surface_counts)


def _score(rows: list[tuple[str, int, float, float]]) -> dict:
    if not rows:
        raise ValueError("empty test fold")
    out: dict = {"n": len(rows)}
    for tag, index in (("coinflip", None), ("global_elo", 2), ("surface_elo", 3)):
        probs = [.5 if index is None else row[index] for row in rows]
        errors = [(p - row[1])**2 for p, row in zip(probs, rows)]
        losses = [-(row[1]*math.log(p) + (1-row[1])*math.log1p(-p))
                  for p, row in zip(probs, rows)]
        out[f"{tag}_brier"] = sum(errors) / len(rows)
        out[f"{tag}_log_loss"] = sum(losses) / len(rows)
    for tag in ("global_elo", "surface_elo"):
        out[f"{tag}_minus_coinflip_log_loss"] = (
            out[f"{tag}_log_loss"] - out["coinflip_log_loss"]
        )
    return out


def _quantile(samples: list[float], q: float) -> float:
    a = sorted(samples)
    x = q*(len(a)-1)
    low = int(x)
    high = min(len(a)-1, low+1)
    return a[low] + (x-low)*(a[high]-a[low])


def _bootstrap(
    years: list[int], predictions: dict[int, list[tuple[str, int, float, float]]],
    *, replicates: int, seed: int,
) -> dict:
    clusters_by_year: list[list[list[tuple[str, int, float, float]]]] = []
    count = 0
    for year in years:
        clusters: dict[str, list[tuple[str, int, float, float]]] = defaultdict(list)
        for item in predictions[year]:
            clusters[item[0]].append(item)
        groups = list(clusters.values())
        count += len(groups)
        clusters_by_year.append(groups)
    result = {
        "status": "INSUFFICIENT_EVENT_SUPPORT",
        "event_clusters": count,
        "replicates": replicates,
        "seed": seed,
        "global_elo_minus_coinflip_95ci": None,
        "surface_elo_minus_coinflip_95ci": None,
    }
    if count < 12 or any(len(groups)<2 for groups in clusters_by_year):
        return result
    rng = random.Random(seed)
    gdiff: list[float] = []
    sdiff: list[float] = []
    for _ in range(replicates):
        sampled: list[tuple[str, int, float, float]] = []
        for groups in clusters_by_year:
            for _ in range(len(groups)):
                sampled.extend(rng.choice(groups))
        scored = _score(sampled)
        gdiff.append(scored["global_elo_minus_coinflip_log_loss"])
        sdiff.append(scored["surface_elo_minus_coinflip_log_loss"])
    result["status"] = "EVENT_BOOTSTRAP_DESCRIPTIVE_ONLY"
    result["global_elo_minus_coinflip_95ci"] = [
        _quantile(gdiff, .025), _quantile(gdiff, .975)
    ]
    result["surface_elo_minus_coinflip_95ci"] = [
        _quantile(sdiff, .025), _quantile(sdiff, .975)
    ]
    return result


def run_tml_elo_experiment(
    paths: Sequence[Path],
    *,
    test_years: tuple[int, ...] = (2023, 2024, 2025),
    embargo_days: int = 28,
    bootstrap_replicates: int = 200,
    seed: int = 29,
    normalize_level_a_2024: bool = False,
) -> dict:
    """Retrospective conditional-matchup study; never executable live odds."""
    if (not isinstance(test_years, tuple) or len(test_years) < 3 or
            any(type(y) is not int for y in test_years) or
            sorted(set(test_years)) != list(test_years)):
        raise ValueError("three or more chronological unique holdout years required")
    if type(embargo_days) is not int or not 14 <= embargo_days <= 90:
        raise ValueError("embargo must be 14 to 90 days")
    if type(bootstrap_replicates) is not int or not 50 <= bootstrap_replicates <= 5000:
        raise ValueError("bootstrap repeats out of bounds")
    if type(seed) is not int:
        raise ValueError("bootstrap seed must be integer")
    if type(normalize_level_a_2024) is not bool:
        raise ValueError("level-A normalization must be an explicit boolean")
    matches, inventory, excluded, date_variants, normalization = _load(
        paths, normalize_level_a_2024=normalize_level_a_2024)
    if not any(m.start.year < test_years[0] for m in matches):
        raise ValueError("insufficient pre-holdout warmup history")
    by_date: dict[date, list[_Match]] = defaultdict(list)
    for m in matches:
        by_date[m.start].append(m)
    days = sorted(by_date)
    predictions: dict[int, list[tuple[str, int, float, float]]] = {
        year: [] for year in test_years
    }
    state = _Ratings()
    matured_index = 0
    for today_index, start in enumerate(days):
        while (matured_index < today_index and
               days[matured_index] + timedelta(days=embargo_days) <= start):
            state.update_matured_date(by_date[days[matured_index]])
            matured_index += 1
        for m in by_date[start]:
            if start.year in predictions:
                p_global, p_surface = state.probabilities(m)
                predictions[start.year].append(
                    (m.event_id, m.outcome_a, p_global, p_surface)
                )

    if any(not predictions[year] for year in test_years):
        raise ValueError("three+ holdout calendar years must contain evaluated matches")
    folds = [{"year": year, **_score(predictions[year])} for year in test_years]
    selected = [m for year in test_years for m in predictions[year]]
    return {
        "status": "HISTORICAL_SKILL_RESEARCH_ONLY",
        "mode": "PERSONAL_NONCOMMERCIAL_RESEARCH",
        "source_inventory": inventory,
        **({"level_a_normalization": normalization} if normalization is not None else {}),
        "source_match_rows_eligible": len(matches),
        "provider_rows_quarantined": (excluded["MALFORMED_ROWS"] + excluded["MISSING_MATCH_ID"]),
        "event_date_variants_grouped": date_variants,
        "excluded_reasons": dict(sorted(excluded.items())),
        "holdout_years": list(test_years),
        "fold_count": len(test_years),
        "test_matches": len(selected),
        "embargo_days_after_tournament_start": embargo_days,
        "elo_k_fixed": 24,
        "surface_weight_fixed": 0.35,
        "folds": folds,
        "aggregate": _score(selected),
        "bootstrap": _bootstrap(list(test_years), predictions,
                                replicates=bootstrap_replicates, seed=seed),
        "participant_known_at_event_start": False,
        "source_result_availability_exact": False,
        "individual_match_time_verified": False,
        "t60_quote_verified": False,
        "market_edge_verified": False,
        "model_validation_trusted": False,
        "allocation_enabled": False,
        "stake": 0,
        "warnings": [
            "EVENT_START_NOT_INDIVIDUAL_MATCH_START",
            "EVALUATED_MATCHUPS_IDENTIFIED_RETROSPECTIVELY",
            "28_DAY_EMBARGO_ESTIMATE_NOT_CONFIRMED_PUBLICATION_TIME",
            "NO_HISTORIC_NO_VIG_MARKET_BASELINE_OR_EXECUTABLE_T60",
            "ELIGIBLE_RESULTS_REQUIRE_INDEPENDENT_OFFICIAL_DRAW_AUDIT",
            "NO_REAL_MONEY_ALLOCATION_OR_PROFIT_CLAIM",
            "BLANK_PROVIDER_MATCH_IDS_ARE_EXCLUDED_NOT_SYNTHESIZED",
            "ONE_DAY_EVENT_START_VARIANTS_GROUPED_TO_EARLIEST_DATE",
        ],
    }
