"""Read-only historical aggregate view; no network, fit, or live prediction."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

EVIDENCE_SHA256 = "6005a0eb688b5d7765d50915abfffb8af471110fb873c6349df9e0b8700a8af6"
FOLDS = ((2023, 2600), (2024, 2647), (2025, 2447))
MATCHES = 7694


def read_historical_evidence(path: Path) -> dict:
    """Read the exact accepted P2.4 aggregate, rejecting missing/altered bytes.

    Accuracy uses fixed equal-width bins: p(A) >= .5 chooses A, including
    exact ties. No individual match rows or model artifacts are exported.
    """
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        raise ValueError("historical evidence unavailable") from exc
    if hashlib.sha256(raw).hexdigest() != EVIDENCE_SHA256:
        raise ValueError("historical evidence SHA256 mismatch")

    evidence = json.loads(raw)
    result = evidence["result"]
    evaluation = result["evaluation"]
    if (
        evidence["schema"] != "P2_4_EXECUTION_EVIDENCE_V1"
        or result["status"] != "HISTORICAL_SKILL_RESEARCH_ONLY"
        or evaluation["status"] != "HISTORICAL_SKILL_RESEARCH_ONLY"
        or result["evaluation_status"] != "PREVIOUSLY_INSPECTED_DEVELOPMENT_YEARS"
        or any(result[key] is not False for key in (
            "allocation_enabled", "model_validation_trusted",
            "future_holdout_accessed", "model_artifact_exported",
        ))
        or result["stake"] != 0
        or evaluation["n"] != MATCHES
        or len(evaluation["models"]) != 18
    ):
        raise ValueError("historical evidence scope or support mismatch")

    models = {}
    for name, row in evaluation["models"].items():
        bins = row["reliability"]
        if (
            row["n"] != MATCHES
            or row["coverage"] != 1.0
            or tuple((f["year"], f["n"]) for f in row["folds"]) != FOLDS
            or [b["bin"] for b in bins] != list(range(10))
            or sum(b["n"] for b in bins) != MATCHES
        ):
            raise ValueError("historical matched support mismatch")
        correct = 0
        for bucket in bins:
            n = bucket["n"]
            if n == 0:
                continue
            wins = round(n * bucket["observed_rate"])
            correct += wins if bucket["bin"] >= 5 else n - wins
        models[name] = {
            "n": row["n"],
            "correct": correct,
            "accuracy": correct / MATCHES,
            "log_loss": row["log_loss"],
            "brier": row["brier"],
            "ece": row["ece"],
            "coverage": row["coverage"],
        }
    return {
        "scope": "HISTORICAL_DEVELOPMENT_ONLY",
        "evidence_sha256": EVIDENCE_SHA256,
        "n": MATCHES,
        "folds": [{"year": year, "n": n} for year, n in FOLDS],
        "models": models,
        "real_data_active": False,
        "model_validation_trusted": False,
    }
