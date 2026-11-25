"""Strict matched-fold ATP forecast scoring, research-only and NOT a model fit.

Scores separately supplied historical probabilities without certifying their
source, point-in-time provenance, bookmaker executability or betting advantage.
"""
from __future__ import annotations

from datetime import date
from math import isfinite, log
from random import Random
from typing import Any


_ALLOWED_TIERS = {"ATP_500", "MASTERS_1000", "GRAND_SLAM"}
_ALLOWED_SURFACES = {"HARD", "CLAY", "GRASS"}
_WINDOW_FIELDS = {"train_end", "calibrate_start", "calibrate_end",
                  "test_start", "test_end", "rows"}
_ROW_FIELDS = {"match_id", "event_id", "date", "outcome_a",
               "p_market", "p_elo", "p_xgb", "tier", "surface"}


def _day(raw: Any) -> date:
    if not isinstance(raw, str) or len(raw) != 10:
        raise ValueError("fold dates must use ISO YYYY-MM-DD")
    try:
        result = date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError("invalid fold date") from exc
    if result.isoformat() != raw:
        raise ValueError("noncanonical fold date")
    return result


def _probability(value: Any, label: str) -> float:
    if (type(value) not in (float, int) or
            not isfinite(value) or not 0.0 < value < 1.0):
        raise ValueError(f"invalid {label} probability")
    return float(value)


def _mean(values: list[float]) -> float:
    if not values:
        raise ValueError("cannot score an empty matched sample")
    return sum(values) / len(values)


def _loss(y: int, p: float) -> float:
    return -(y * log(p) + (1 - y) * log(1 - p))


def _score(rows: list[dict]) -> dict:
    out: dict[str, Any] = {"n": len(rows)}
    for tag in ("market", "elo", "xgb"):
        probs = [row[f"p_{tag}"] for row in rows]
        outcomes = [row["outcome_a"] for row in rows]
        out[f"{tag}_log_loss"] = _mean([
            _loss(y, p) for y, p in zip(outcomes, probs)
        ])
        out[f"{tag}_brier"] = _mean([
            (p - y) ** 2 for y, p in zip(outcomes, probs)
        ])
    out["xgb_minus_market_log_loss"] = (
        out["xgb_log_loss"] - out["market_log_loss"])
    out["elo_minus_market_log_loss"] = (
        out["elo_log_loss"] - out["market_log_loss"])
    return out


def _quantile(samples: list[float], fraction: float) -> float:
    sorted_values = sorted(samples)
    index = fraction * (len(sorted_values) - 1)
    lower = int(index)
    upper = min(lower + 1, len(sorted_values) - 1)
    return sorted_values[lower] + (index - lower) * (
        sorted_values[upper] - sorted_values[lower]
    )


def _paired_event_bootstrap(
    validated_folds: list[list[dict]], *, seed: int, replicates: int,
) -> dict:
    fold_clusters: list[list[list[dict]]] = []
    unique_count = 0
    for rows in validated_folds:
        grouped: dict[str, list[dict]] = {}
        for row in rows:
            grouped.setdefault(row["event_id"], []).append(row)
        clusters = list(grouped.values())
        fold_clusters.append(clusters)
        unique_count += len(clusters)

    result: dict = {
        "status": "INSUFFICIENT_CLUSTER_SUPPORT",
        "unique_event_clusters": unique_count,
        "bootstrap_replicates": replicates,
        "bootstrap_seed": seed,
        "xgb_minus_market_95ci": None,
        "elo_minus_market_95ci": None,
    }
    if unique_count < 6 or any(len(clusters) < 2 for clusters in fold_clusters):
        return result

    rng = Random(seed)
    dx: list[float] = []
    de: list[float] = []
    for _ in range(replicates):
        selected: list[dict] = []
        for clusters in fold_clusters:
            for _j in range(len(clusters)):
                selected.extend(rng.choice(clusters))
        scored = _score(selected)
        dx.append(scored["xgb_minus_market_log_loss"])
        de.append(scored["elo_minus_market_log_loss"])

    result["status"] = "CLUSTER_BOOTSTRAP_DESCRIPTIVE_ONLY"
    result["xgb_minus_market_95ci"] = [
        _quantile(dx, 0.025), _quantile(dx, 0.975),
    ]
    result["elo_minus_market_95ci"] = [
        _quantile(de, 0.025), _quantile(de, 0.975),
    ]
    return result


def audit_fold_scores(
    folds: list[dict], *, bootstrap_replicates: int = 400,
    seed: int = 20261124,
) -> dict:
    """Score exactly matched forecast rows in 3+ disjoint future holdouts.

    This does NOT verify the predictions were actually produced out-of-sample
    or that any quoted market probability existed at the prediction cutoff.
    """
    if not isinstance(folds, list) or len(folds) < 3:
        raise ValueError("at least three dated evaluation folds required")
    if (type(bootstrap_replicates) is not int or
            not 50 <= bootstrap_replicates <= 10000):
        raise ValueError("bootstrap replicates must be 50..10000")
    if type(seed) is not int:
        raise ValueError("bootstrap seed must be integer")

    previous_end: date | None = None
    previous_train_end: date | None = None
    seen_ids: set[str] = set()
    validated: list[list[dict]] = []
    reports: list[dict] = []

    for number, fold in enumerate(folds, start=1):
        if not isinstance(fold, dict) or set(fold) != _WINDOW_FIELDS:
            raise ValueError("invalid evaluation fold schema")
        dates = {key: _day(fold[key]) for key in _WINDOW_FIELDS if key != "rows"}
        if not (
            dates["train_end"] < dates["calibrate_start"]
            <= dates["calibrate_end"] < dates["test_start"]
            <= dates["test_end"]
        ):
            raise ValueError("train/calibration/holdout windows overlap")
        if previous_end is not None and dates["test_start"] <= previous_end:
            raise ValueError("nonchronological or overlapping future holdout")
        if previous_train_end is not None and dates["train_end"] <= previous_train_end:
            raise ValueError("expanding training cutoff must strictly increase")
        previous_end = dates["test_end"]
        previous_train_end = dates["train_end"]

        rows = fold["rows"]
        if not isinstance(rows, list) or not rows:
            raise ValueError("empty holdout fold")
        normalized: list[dict] = []
        for raw in rows:
            if not isinstance(raw, dict) or set(raw) != _ROW_FIELDS:
                raise ValueError("row missing paired model/market probability")
            match_id, event_id = raw["match_id"], raw["event_id"]
            if (not isinstance(match_id, str) or not match_id.strip()
                    or not isinstance(event_id, str) or not event_id.strip()):
                raise ValueError("invalid match/event identity")
            if match_id in seen_ids:
                raise ValueError("duplicate match ID across fold holdouts")
            seen_ids.add(match_id)
            match_date = _day(raw["date"])
            if not dates["test_start"] <= match_date <= dates["test_end"]:
                raise ValueError("test-row date outside disjoint holdout window")
            y = raw["outcome_a"]
            if type(y) is not int or y not in (0, 1):
                raise ValueError("binary match outcome must be int 0 or 1")
            if raw["tier"] not in _ALLOWED_TIERS or raw["surface"] not in _ALLOWED_SURFACES:
                raise ValueError("unsupported competition tier or surface")
            normalized.append({
                "match_id": match_id, "event_id": event_id,
                "outcome_a": y,
                "p_market": _probability(raw["p_market"], "market"),
                "p_elo": _probability(raw["p_elo"], "elo"),
                "p_xgb": _probability(raw["p_xgb"], "xgb"),
                "tier": raw["tier"], "surface": raw["surface"],
            })
        validated.append(normalized)
        reports.append({
            "fold": number,
            "train_end": dates["train_end"].isoformat(),
            "calibrate_start": dates["calibrate_start"].isoformat(),
            "calibrate_end": dates["calibrate_end"].isoformat(),
            "test_start": dates["test_start"].isoformat(),
            "test_end": dates["test_end"].isoformat(),
            **_score(normalized),
        })

    all_rows = [row for fold_rows in validated for row in fold_rows]
    return {
        "status": "UNTRUSTED_FORECAST_EVALUATION_ONLY",
        "mode": "HISTORICAL_RESEARCH_ONLY",
        "fold_count": len(folds),
        "matched_test_n": len(all_rows),
        "folds": reports,
        "aggregate": _score(all_rows),
        "paired_uncertainty": _paired_event_bootstrap(
            validated, seed=seed, replicates=bootstrap_replicates,
        ),
        "source_rights_verified": False,
        "asof_feature_provenance_verified": False,
        "t60_quote_verified": False,
        "market_edge_verified": False,
        "validation_report_trusted": False,
        "eligible_for_model_training": 0,
        "allocation_enabled": False,
        "stake": 0,
        "warnings": [
            "PREDICTION_ORIGIN_AND_ASOF_TIMESTAMPS_NOT_VERIFIED",
            "HISTORICAL_MARKET_BASELINE_NOT_EXECUTABLE_T60_QUOTE",
            "NO_PROOF_OF_TRADABLE_EDGE_OR_PROFIT",
            "PAIRING_MATCHED_WITHIN_SUBMITTED_SAMPLE_ONLY",
            "SOURCE_COMPLETENESS_AND_LICENSE_REVIEW_REQUIRED",
        ],
    }
