"""Fixed pre-registered Elo variants and feature blocks for historical development."""
from collections import Counter, defaultdict
import math

from .tml_development_data import validate_matches, EMBARGO
from .tml_development_features import FEATURE_NAMES
from .tml_elo_experiment import _Ratings, _elo_p

FEATURE_BLOCKS = {
    "elo_only": FEATURE_NAMES[:3],
    "elo_history": FEATURE_NAMES[:15],
    "all": FEATURE_NAMES,
}


def build_elo_variants(matches):
    """Same 28-day release and prebatch state, one change per baseline.

    Convex uses unchanged overall/surface baseline ratings; decay uses
    per-player experience before the batch; mean uses average residual.
    No same-date outcomes or within-event result ordering in predictions.
    """
    rows = validate_matches(matches)
    by_date = defaultdict(list)
    for m in rows:
        by_date[m.start].append(m)
    days = sorted(by_date)
    ratings = _Ratings()
    decay, mean = {}, {}
    count = Counter()
    result = {n: {} for n in ("convex_surface", "decay_k", "mean_batch")}
    cursor = 0
    for i, today in enumerate(days):
        while cursor < i and days[cursor] + EMBARGO <= today:
            batch = by_date[days[cursor]]
            ratings.update_matured_date(batch)
            decay_residuals, mean_residuals = defaultdict(list), defaultdict(list)
            for m in batch:
                a, b = m.player_a, m.player_b
                dr = m.outcome_a - _elo_p(decay.get(a, 1500.), decay.get(b, 1500.))
                mr = m.outcome_a - _elo_p(mean.get(a, 1500.), mean.get(b, 1500.))
                decay_residuals[a].append(dr)
                decay_residuals[b].append(-dr)
                mean_residuals[a].append(mr)
                mean_residuals[b].append(-mr)
            for p, residuals in decay_residuals.items():
                decay[p] = decay.get(p, 1500.) + 250 / (count[p] + 5)**.4 * math.fsum(residuals)
                count[p] += len(residuals)
            for p, residuals in mean_residuals.items():
                mean[p] = mean.get(p, 1500.) + 24 * math.fsum(residuals) / len(residuals)
            cursor += 1
        for m in by_date[today]:
            a, b = m.player_a, m.player_b
            def blend(p):
                k = p, m.surface
                n = ratings.surface_n[k]
                w = .35 * n / (n + 20)
                return (1 - w) * ratings.overall.get(p, 1500.) + w * ratings.surface.get(k, 1500.)
            result["convex_surface"][m.key] = _elo_p(blend(a), blend(b))
            result["decay_k"][m.key] = _elo_p(decay.get(a, 1500.), decay.get(b, 1500.))
            result["mean_batch"][m.key] = _elo_p(mean.get(a, 1500.), mean.get(b, 1500.))
    return result
