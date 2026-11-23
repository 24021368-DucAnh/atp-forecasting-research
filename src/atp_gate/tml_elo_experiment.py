"""Source-pinned pre-tournament Elo SKILL study for personal ATP research only.

TML tourney_date is an event START date, not a match date. We score
retrospectively observed matchups with ratings frozen before each tournament
and embargo all outcomes for 28 days. Nothing here certifies an executable
prematch pairing, real-time quote, profitable bet, or model release.
"""
from __future__ import annotations

import csv
import hashlib
import math
import random
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Sequence

from .tml_historical_audit import TML_COLUMNS

_ALLOWED_LEVELS = frozenset({"250", "500", "M", "G"})
_ALLOWED_SURFACES = frozenset({"Hard", "Clay", "Grass"})
_BAD_SCORES = re.compile(r"\b(?:RET|W/O|WO|WALKOVER|DEF|ABN|ABD|CANCELLED)\b", re.I)
_FILENAME = re.compile(r"^(\d{4})(?:-([0-9a-f]{64}))?\.csv$")
_SOURCE_CAP = 20 * 1024 * 1024


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
    if not (isinstance(winner_id, str) and isinstance(loser_id, str)
            and winner_id.strip() and loser_id.strip() and winner_id != loser_id):
        raise ValueError("invalid player identity pair")
    a, b = sorted((winner_id, loser_id))
    return a, b, int(winner_id == a)


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


def _load(paths: Sequence[Path]) -> tuple[list[_Match], list[dict], Counter]:
    if not isinstance(paths, (list, tuple)) or len(paths) < 4:
        raise ValueError("four or more local source seasons required")
    inventory: list[dict] = []
    events: list[_Match] = []
    excluded: Counter = Counter()
    seen_seasons: set[int] = set()
    seen_match_keys: set[tuple[str, str]] = set()
    event_metadata: dict[str, tuple[date, str]] = {}

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
                    raise ValueError("invalid TML source CSV row column count")
                tid, mid = row["tourney_id"], row["match_num"]
                if not tid or not mid:
                    raise ValueError("source tournament/match ID missing")
                key = (tid, mid)
                if key in seen_match_keys:
                    raise ValueError("duplicate TML tournament/match identity")
                seen_match_keys.add(key)
                start = _source_date(row["tourney_date"], season)
                surface = row["surface"]
                prior_meta = event_metadata.setdefault(tid, (start, surface))
                if prior_meta != (start, surface):
                    raise ValueError("conflicting TML tournament start or surface")
                if row["tourney_level"] not in _ALLOWED_LEVELS:
                    excluded["OUT_OF_SCOPE_LEVEL"] += 1
                    continue
                if surface not in _ALLOWED_SURFACES:
                    excluded["UNKNOWN_SURFACE"] += 1
                    continue
                score = row["score"]
                if not score or not any(x.isdigit() for x in score) or _BAD_SCORES.search(score):
                    excluded["NON_COMPLETED"] += 1
                    continue
                if not row["winner_id"] or not row["loser_id"] or row["winner_id"] == row["loser_id"]:
                    excluded["INVALID_PLAYER_ID"] += 1
                    continue
                a, b, y = orient_result(row["winner_id"], row["loser_id"])
                events.append(_Match(tid, start, surface, a, b, y))
            inventory.append({
                "season": season,
                "source_file": path.name,
                "sha256": sha,
                "size_bytes": len(payload),
                "source_rows": count,
                "source_url": f"https://stats.tennismylife.org/data/{season}.csv",
            })
        except (UnicodeError, csv.Error) as exc:
            raise ValueError("invalid TML source UTF-8/CSV encoding") from exc

    if not events:
        raise ValueError("no eligible completed tour-level TML matches")
    return events, sorted(inventory, key=lambda x: x["season"]), excluded


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
    matches, inventory, excluded = _load(paths)
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
        "source_match_rows_eligible": len(matches),
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
        ],
    }
