"""Descriptive synthetic metrics; never ranks unmatched denominators."""
from dataclasses import asdict, dataclass
import math

EPSILON = 1e-12


@dataclass(frozen=True)
class CalibrationBin:
    index: int
    n: int
    mean_probability: float | None
    outcome_rate: float | None


@dataclass(frozen=True)
class Metrics:
    n: int
    accuracy: float | None
    brier: float | None
    log_loss: float | None
    ece: float | None
    bins: tuple[CalibrationBin, ...]


def _sample(row):
    if type(row) not in (tuple, list) or len(row) != 2:
        raise ValueError("expected probability and binary outcome")
    p, y = row
    if (type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1
            or type(y) is not int or y not in (0, 1)):
        raise ValueError("invalid probability or outcome")
    return float(p), y


def score_metrics(rows) -> Metrics:
    samples = tuple(_sample(row) for row in rows)
    groups = [[] for _ in range(10)]
    for p, y in samples:
        groups[min(9, int(10 * p))].append((p, y))
    bins = tuple(CalibrationBin(j, len(g),
                                math.fsum(p for p, _ in g) / len(g) if g else None,
                                math.fsum(y for _, y in g) / len(g) if g else None)
                 for j, g in enumerate(groups))
    n = len(samples)
    if not n:
        return Metrics(0, None, None, None, None, bins)
    accuracy = sum(int(p >= .5) == y for p, y in samples) / n
    brier = math.fsum((p - y) ** 2 for p, y in samples) / n
    losses = []
    for p, y in samples:
        q = max(EPSILON, min(1. - EPSILON, p))
        losses.append(-math.log(q) if y else -math.log1p(-q))
    ece = math.fsum(b.n * abs(b.mean_probability - b.outcome_rate)
                    for b in bins if b.n) / n
    return Metrics(n, accuracy, brier, math.fsum(losses) / n, ece, bins)


def matched_metrics(models):
    """Map model -> fixture -> (p_A, y_A, result revision ID).

    Only the exact common fixture/outcome/revision intersection is
    comparable. Per-model unmatched counts are explicit; no ranking.
    """
    if type(models) is not dict:
        raise ValueError("invalid model sample mapping")
    cleaned = {}
    for model, rows in models.items():
        if type(model) is not str or not model or type(rows) is not dict:
            raise ValueError("invalid model sample mapping")
        current = {}
        for key, row in rows.items():
            if (type(key) is not str or not key or type(row) not in (tuple, list)
                    or len(row) != 3 or type(row[2]) is not str or not row[2]):
                raise ValueError("invalid matched observation")
            p, y = _sample(row[:2])
            current[key] = (p, y, row[2])
        cleaned[model] = current
    names = sorted(cleaned)
    common = set.intersection(*(set(cleaned[name]) for name in names)) if len(names) >= 2 else set()
    keys = tuple(sorted(key for key in common
                        if len({cleaned[name][key][1:] for name in names}) == 1))
    return {
        "matched_keys": keys, "matched_n": len(keys),
        "models": {name: asdict(score_metrics(cleaned[name][key][:2] for key in keys)) for name in names},
        "available_n": {name: len(cleaned[name]) for name in names},
        "unmatched_n": {name: len(cleaned[name]) - len(keys) for name in names},
    }
