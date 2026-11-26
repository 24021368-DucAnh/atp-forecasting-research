"""Synthetic label-free feature engine matching frozen V3 feature mathematics."""
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from hashlib import sha256
from itertools import groupby
import json
import math

from atp_lab.database.identity import utc_timestamp
from .temporal import UpcomingFixture, HistoricalResult, TemporalError
from .temporal import normalize_fixture, select_history

FEATURE_VERSION = "V4_SYNTHETIC_V3_FEATURES_1"
FEATURE_NAMES = (
    "overall_elo_diff", "surface_elo_diff", "surface_shrinkage_elo_diff",
    "log1p_total_history_diff", "log1p_surface_history_diff", "win_rate_90d_diff",
    "win_rate_365d_diff", "log1p_90d_count_diff", "log1p_365d_count_diff",
    "smoothed_h2h_diff", "log1p_h2h_count", "min_history", "min_surface_history",
    "both_have_history", "both_have_surface_history", "surface_hard",
    "surface_clay", "surface_grass",
)


@dataclass(frozen=True)
class FeatureSnapshot:
    fixture_id: str
    cutoff: str
    values: tuple[tuple[str, int | float], ...]
    result_ids: tuple[str, ...]
    digest: str


def _elo_p(a: float, b: float) -> float:
    z = max(-15., min(15., (a - b) / 400.))
    p = 1. / (1. + 10. ** (-z))
    return min(1. - 1e-12, max(1e-12, p))


def _feature_values(target: UpcomingFixture,
                    selected: tuple[HistoricalResult, ...]) -> tuple:
    overall = {}
    surface = {}
    surface_n = Counter()
    total = Counter()
    meetings = Counter()
    wins = Counter()
    history = defaultdict(list)
    event_meta = {}
    for row in selected:
        meta = (row.event_start, row.surface)
        if event_meta.setdefault(row.tournament_id, meta) != meta:
            raise TemporalError("inconsistent selected event metadata")

    # Each event-start date batch uses frozen prior ratings. No updates
    # from an earlier match in the same batch affect another match.
    for _, batch in groupby(selected, key=lambda row: row.event_start):
        global_delta = defaultdict(float)
        surface_delta = defaultdict(float)
        counts = Counter()
        for row in batch:
            a, b = row.player_a, row.player_b
            ka, kb = (a, row.surface), (b, row.surface)
            outcome = int(row.winner == a)
            step = 24. * (outcome - _elo_p(overall.get(a, 1500.),
                                             overall.get(b, 1500.)))
            global_delta[a] += step
            global_delta[b] -= step
            step = 24. * (outcome - _elo_p(surface.get(ka, 1500.),
                                             surface.get(kb, 1500.)))
            surface_delta[ka] += step
            surface_delta[kb] -= step
            counts.update((ka, kb))
            total.update((a, b))
            meetings[(a, b)] += 1
            wins[(a, b)] += outcome
            history[a].append((row.event_start, outcome))
            history[b].append((row.event_start, 1 - outcome))
        for key, delta in global_delta.items():
            overall[key] = overall.get(key, 1500.) + delta
        for key, delta in surface_delta.items():
            surface[key] = surface.get(key, 1500.) + delta
        surface_n.update(counts)

    def window(player, days):
        outcomes = [y for d, y in history[player]
                    if (target.event_start - d).days <= days]
        n = len(outcomes)
        return (sum(outcomes) + 1) / (n + 2), n

    a, b = target.player_a, target.player_b
    ka, kb = (a, target.surface), (b, target.surface)
    ga, gb = overall.get(a, 1500.), overall.get(b, 1500.)
    sa, sb = surface.get(ka, 1500.), surface.get(kb, 1500.)
    na, nb = surface_n[ka], surface_n[kb]
    xa = ga + .35 * na / (na + 20) * (sa - 1500)
    xb = gb + .35 * nb / (nb + 20) * (sb - 1500)
    f90a, n90a = window(a, 90)
    f90b, n90b = window(b, 90)
    f365a, n365a = window(a, 365)
    f365b, n365b = window(b, 365)
    count = meetings[(a, b)]
    return (
        ga - gb, sa - sb, xa - xb,
        math.log1p(total[a]) - math.log1p(total[b]),
        math.log1p(na) - math.log1p(nb),
        f90a - f90b, f365a - f365b,
        math.log1p(n90a) - math.log1p(n90b),
        math.log1p(n365a) - math.log1p(n365b),
        2 * (wins[(a, b)] + 1) / (count + 2) - 1,
        math.log1p(count), min(total[a], total[b]), min(na, nb),
        int(min(total[a], total[b]) > 0), int(min(na, nb) > 0),
        int(target.surface == "HARD"), int(target.surface == "CLAY"),
        int(target.surface == "GRASS"),
    )


def _metadata(row):
    data = asdict(row)
    data["event_start"] = row.event_start.isoformat()
    return data


def build_feature_snapshot(
    fixture: UpcomingFixture,
    results: tuple[HistoricalResult, ...] | list[HistoricalResult],
    *, cutoff: str,
) -> FeatureSnapshot:
    """Build immutable ordered features using eligible synthetic history only.

    Digest binds normalized input lineage and values, not authenticated
    timestamps or real provider permissions. No target labels or DB writes.
    """
    target = normalize_fixture(fixture, cutoff=cutoff)
    limit = utc_timestamp(cutoff)
    selected = select_history(target, results, cutoff=limit)
    values = tuple(zip(FEATURE_NAMES, _feature_values(target, selected)))
    if any(type(v) not in (int, float) or not math.isfinite(v) for _, v in values):
        raise TemporalError("nonfinite feature value")
    evidence = {
        "version": FEATURE_VERSION,
        "fixture": _metadata(target),
        "cutoff": limit,
        "results": [_metadata(row) for row in selected],
        "features": values,
    }
    digest = sha256(json.dumps(evidence, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=True, allow_nan=False).encode("utf-8")).hexdigest()
    return FeatureSnapshot(target.fixture_id, limit, values,
                           tuple(row.result_id for row in selected), digest)
