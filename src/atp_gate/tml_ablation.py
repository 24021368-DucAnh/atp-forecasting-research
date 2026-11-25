"""Fixed pre-registered Elo variants and feature blocks for historical development."""
from collections import Counter, defaultdict
import math

from .tml_development_data import validate_matches, EMBARGO, YEARS
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


_REPEAT_MODELS = frozenset({
    "coinflip", "global_elo", "surface_elo", "logistic_raw",
    "logistic_platt", "logistic_isotonic", "xgboost_raw",
    "xgboost_platt", "xgboost_isotonic",
})
_BOOTSTRAP_STRINGS = {
    "assumptions": "EVENT_CLUSTER_RESAMPLING_NOT_PROOF_OF_INDEPENDENCE",
    "cluster_unit": "EVENT_ID",
    "estimand": "MATCH_WEIGHTED_MEAN_LOSS_DIFFERENCE",
    "interval_method": "PAIRED_PERCENTILE_95",
    "sampling_scope": "FIXED_HISTORICAL_PREDICTIONS_NO_REFIT",
    "status": "EVENT_BOOTSTRAP_DESCRIPTIVE_ONLY",
    "stratification": "EVENT_START_CALENDAR_YEAR",
}


def _finite_number(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _repeat_support(row):
    if not isinstance(row, dict):
        raise ValueError("invalid repeat comparison model")

    def support(entry):
        if not isinstance(entry, dict):
            raise ValueError("invalid repeat comparison fold")
        n, coverage = entry.get("n"), entry.get("coverage")
        if (type(n) is not int or n <= 0 or not _finite_number(coverage)
                or coverage != 1):
            raise ValueError("invalid repeat comparison matched support")
        return n, coverage

    total = support(row)
    folds = row.get("folds")
    if not isinstance(folds, list) or len(folds) != len(YEARS):
        raise ValueError("repeat comparison fold support mismatch")
    entries = []
    for expected_year, fold in zip(YEARS, folds):
        n, coverage = support(fold)
        year = fold.get("year")
        if type(year) is not int or year != expected_year:
            raise ValueError("invalid repeat comparison fold year")
        entries.append((year, n, coverage))
    if sum(entry[1] for entry in entries) != total[0]:
        raise ValueError("repeat comparison fold total mismatch")
    return total, tuple(entries)


def _repeat_bootstrap(row):
    if not isinstance(row, dict):
        raise ValueError("missing repeat comparison intervals")
    boot = row.get("bootstrap")
    if (not isinstance(boot, dict)
            or any(boot.get(k) != v for k, v in _BOOTSTRAP_STRINGS.items())
            or type(boot.get("seed")) is not int or boot["seed"] != 29
            or type(boot.get("replicates")) is not int or boot["replicates"] != 2000
            or row.get("brier_ci_probability_semantics") != "CLIPPED_AT_1E_12_FOR_BOOTSTRAP_NUMERICS"):
        raise ValueError("invalid repeat comparison bootstrap contract")
    counts = boot.get("event_clusters_by_year")
    total = boot.get("event_clusters")
    if (not isinstance(counts, dict) or set(counts) != {str(y) for y in YEARS}
            or any(type(n) is not int or n <= 0 for n in counts.values())
            or type(total) is not int or total != sum(counts.values())):
        raise ValueError("invalid repeat comparison bootstrap cluster support")
    return boot


def compare_repeated_models(previous, current):
    """Compare registered P2.3 models on matched historical evaluation support.

    Extra P2.4 ablations are deliberately excluded from the repeat comparison.
    Signed differences are current minus previous, not a new acceptance threshold.
    """
    if (not isinstance(previous, dict) or not isinstance(current, dict)
            or set(previous) != _REPEAT_MODELS or not _REPEAT_MODELS <= current.keys()):
        raise ValueError("repeat comparison model set mismatch")

    def number(row, key):
        value = row.get(key)
        if not _finite_number(value):
            raise ValueError(f"invalid repeat comparison metric: {key}")
        return value

    def difference(new, old):
        value = new - old
        if not _finite_number(value):
            raise ValueError("nonfinite repeat comparison difference")
        return value

    def interval(row, metric):
        value = row.get(metric)
        if (not isinstance(value, list) or len(value) != 2
                or any(not _finite_number(x) for x in value)
                or value[0] > value[1]):
            raise ValueError(f"invalid repeat comparison interval: {metric}")
        return value

    baseline = _repeat_support(previous["global_elo"])
    repeated = {}
    for name, old in previous.items():
        new = current[name]
        if _repeat_support(old) != baseline or _repeat_support(new) != baseline:
            raise ValueError(f"repeat comparison evaluation support mismatch: {name}")
        pairs = [(old, new), *zip(old["folds"], new["folds"])]
        result = {
            "max_abs_proper_score_difference": max(
                abs(difference(number(b, k), number(a, k)))
                for a, b in pairs for k in ("log_loss", "brier")
            ),
            "aggregate_ece_difference": difference(number(new, "ece"), number(old, "ece")),
            "bootstrap_endpoint_differences": None,
            "max_abs_bootstrap_endpoint_difference": None,
        }
        if name != "global_elo":
            a, b = old.get("minus_global_elo"), new.get("minus_global_elo")
            if _repeat_bootstrap(a) != _repeat_bootstrap(b):
                raise ValueError(f"repeat comparison bootstrap contract mismatch: {name}")
            differences = {}
            for metric in ("log_loss_95ci", "brier_95ci"):
                x, y = interval(a, metric), interval(b, metric)
                differences[metric] = [difference(y[0], x[0]), difference(y[1], x[1])]
            result["bootstrap_endpoint_differences"] = differences
            result["max_abs_bootstrap_endpoint_difference"] = max(
                abs(x) for endpoints in differences.values() for x in endpoints
            )
        elif "minus_global_elo" in old or "minus_global_elo" in new:
            raise ValueError("global Elo must not contain self-comparison intervals")
        repeated[name] = result
    return repeated
