"""Synthetic lifecycle demonstration, not a real holdout or security boundary."""
import hashlib
import json
import math
import re

from .p2_5_synthetic_gate import validate_synthetic_request


def _validated_rows(rows, fields):
    if type(rows) is not list or not rows:
        raise ValueError("nonempty synthetic rows required")
    result = {}
    for row in rows:
        if type(row) is not dict or row.keys() != fields:
            raise ValueError("invalid synthetic row schema")
        key = row["id"]
        if (type(key) is not str
                or re.fullmatch(r"SYN-[A-Z0-9]+(?:-[A-Z0-9]+)*", key) is None
                or key in result):
            raise ValueError("invalid or duplicate synthetic key")
        if "feature" in fields:
            value = row["feature"]
            if type(value) not in (int, float) or not 0 <= value <= 1:
                raise ValueError("invalid synthetic feature")
        if "outcome" in fields:
            value = row["outcome"]
            if type(value) is not int or value not in (0, 1):
                raise ValueError("invalid synthetic outcome")
        result[key] = dict(row)
        if "feature" in fields:
            result[key]["feature"] = 0.0 if row["feature"] == 0 else float(row["feature"])
    return result


class SyntheticSession:
    """Single in-memory simulation; role strings are not authenticated identities."""

    def __init__(self, request: dict):
        receipt = validate_synthetic_request(request)
        self._request = dict(request)
        self._receipt = receipt
        self._state = "AUTHORIZED"

    def _require(self, state):
        if self._state != state:
            raise ValueError("invalid synthetic lifecycle state")

    def fit(self, rows: list[dict]) -> None:
        self._require("AUTHORIZED")
        training = _validated_rows(rows, {"id", "feature", "outcome"})
        counts = [0, 0]
        wins = [0, 0]
        for row in training.values():
            i = int(row["feature"] >= 0.5)
            counts[i] += 1
            wins[i] += row["outcome"]
        self._training = tuple(training[k] for k in sorted(training))
        self._probabilities = tuple((w + 1) / (n + 2) for w, n in zip(wins, counts))
        self._state = "FITTED"

    def _state_digest(self):
        payload = {
            "schema": "SYNTHETIC_TWO_BIN_V2",
            "request": self._request,
            "training": self._training,
            "probabilities": self._probabilities,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _prediction_commitment(self, predictions):
        if type(predictions) is not dict or not predictions:
            raise ValueError("invalid synthetic prediction map")
        for key, value in predictions.items():
            if (type(key) is not str
                    or re.fullmatch(r"SYN-[A-Z0-9]+(?:-[A-Z0-9]+)*", key) is None
                    or type(value) is not float or not 0 < value < 1):
                raise ValueError("invalid synthetic prediction commitment")
        payload = {
            "schema": "SYNTHETIC_PREDICTIONS_V2",
            "frozen_digest": self._digest,
            "predictions": predictions,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def freeze(self) -> str:
        self._require("FITTED")
        self._digest = self._state_digest()
        self._state = "FROZEN"
        return self._digest

    def predict(self, rows: list[dict], *, digest: str) -> None:
        self._require("FROZEN")
        if (type(digest) is not str or digest != self._digest
                or self._state_digest() != self._digest):
            raise ValueError("synthetic frozen commitment mismatch")
        matchups = _validated_rows(rows, {"id", "feature"})
        if matchups.keys() & {row["id"] for row in self._training}:
            raise ValueError("synthetic training/evaluation overlap")
        predictions = {
            key: self._probabilities[int(row["feature"] >= 0.5)]
            for key, row in matchups.items()
        }
        commitment = self._prediction_commitment(predictions)
        self._predictions = predictions
        self._prediction_digest = commitment
        self._state = "PREDICTED"

    def release(self, labels: list[dict], *, custodian_id: str) -> dict:
        self._require("PREDICTED")
        if type(custodian_id) is not str or custodian_id != self._request["custodian_id"]:
            raise ValueError("wrong simulated custodian")
        if self._state_digest() != self._digest:
            raise ValueError("synthetic frozen commitment mismatch")
        if self._prediction_commitment(self._predictions) != self._prediction_digest:
            raise ValueError("synthetic prediction commitment mismatch")
        outcomes = _validated_rows(labels, {"id", "outcome"})
        if outcomes.keys() != self._predictions.keys():
            raise ValueError("synthetic matched-key coverage mismatch")
        pairs = [(outcomes[k]["outcome"], self._predictions[k]) for k in sorted(outcomes)]
        n = len(pairs)
        report = {
            **self._receipt,
            "commitment_schema": "SYNTHETIC_TWO_BIN_V2",
            "frozen_digest": self._digest,
            "prediction_digest": self._prediction_digest,
            "n": n,
            "coverage": 1.0,
            "log_loss": math.fsum(-math.log(p if y else 1 - p) for y, p in pairs) / n,
            "brier": math.fsum((p - y) ** 2 for y, p in pairs) / n,
        }
        self._state = "RELEASED"
        return report
