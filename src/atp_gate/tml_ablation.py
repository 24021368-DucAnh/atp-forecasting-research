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


def compare_repeated_models(previous, current):
    """Compare the archived P2.3 models against identical evaluation support.

    Extra P2.4 ablations are deliberately excluded from the repeat comparison.
    Signed differences are current minus previous, not a new acceptance threshold.
    """
    if "global_elo" not in previous or not previous.keys() <= current.keys():
        raise ValueError("repeat comparison missing model")

    def number(row, key):
        value = row.get(key)
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError(f"invalid repeat comparison metric: {key}")
        return value

    def interval(row, metric):
        value = row.get(metric)
        if (not isinstance(value, list) or len(value) != 2
                or any(type(x) not in (int, float) or not math.isfinite(x) for x in value)
                or value[0] > value[1]):
            raise ValueError(f"invalid repeat comparison interval: {metric}")
        return value

    repeated = {}
    for name, old in previous.items():
        new = current[name]
        old_folds, new_folds = old.get("folds"), new.get("folds")
        if (not isinstance(old_folds, list) or not isinstance(new_folds, list)
                or len(old_folds) != len(new_folds) or not old_folds):
            raise ValueError(f"repeat comparison fold support mismatch: {name}")
        pairs = [(old, new), *zip(old_folds, new_folds)]
        if any((a.get("year"), a.get("n"), a.get("coverage")) !=
               (b.get("year"), b.get("n"), b.get("coverage")) for a, b in pairs):
            raise ValueError(f"repeat comparison evaluation support mismatch: {name}")
        result = {
            "max_abs_proper_score_difference": max(
                abs(number(a, k) - number(b, k))
                for a, b in pairs for k in ("log_loss", "brier")
            ),
            "aggregate_ece_difference": number(new, "ece") - number(old, "ece"),
            "bootstrap_endpoint_differences": None,
            "max_abs_bootstrap_endpoint_difference": None,
        }
        if name != "global_elo":
            a, b = old.get("minus_global_elo"), new.get("minus_global_elo")
            if not isinstance(a, dict) or not isinstance(b, dict):
                raise ValueError(f"missing repeat comparison intervals: {name}")
            if (not isinstance(a.get("bootstrap"), dict)
                    or a["bootstrap"] != b.get("bootstrap")
                    or a.get("brier_ci_probability_semantics") != b.get("brier_ci_probability_semantics")):
                raise ValueError(f"repeat comparison bootstrap contract mismatch: {name}")
            differences = {}
            for metric in ("log_loss_95ci", "brier_95ci"):
                x, y = interval(a, metric), interval(b, metric)
                differences[metric] = [y[0] - x[0], y[1] - x[1]]
            result["bootstrap_endpoint_differences"] = differences
            result["max_abs_bootstrap_endpoint_difference"] = max(
                abs(x) for endpoints in differences.values() for x in endpoints
            )
        elif "minus_global_elo" in old or "minus_global_elo" in new:
            raise ValueError("global Elo must not contain self-comparison intervals")
        repeated[name] = result
    return repeated
