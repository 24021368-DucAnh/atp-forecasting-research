"""Bounded canonical synthetic logistic artifact, never pickle or joblib."""
from dataclasses import asdict, dataclass
import json
import math
import os
from pathlib import Path
import stat
import tempfile

from atp_lab.database.identity import utc_timestamp
from atp_lab.prediction.commitment import _hash, _json
from atp_lab.prediction.features import FEATURE_NAMES, FEATURE_VERSION
from .dataset import TrainingDataset, decode_dataset, feature_vector
from .protocol import (TrainingProtocol, decode_protocol, fixed_config,
                       protocol_payload, require_digest)

ARTIFACT_VERSION = "S6_SYNTHETIC_LOGISTIC_JSON_1"
MAX_BYTES = 8 * 1024 * 1024
EPSILON = 1e-12
MODEL_PREFIX = "SYN-logistic-"


def clip(p):
    if not math.isfinite(p):
        raise ValueError("nonfinite probability")
    return min(1. - EPSILON, max(EPSILON, p))


def sigmoid(z):
    if not math.isfinite(z):
        raise ValueError("nonfinite logit")
    if z >= 0:
        return 1. / (1. + math.exp(-z))
    e = math.exp(z)
    return e / (1. + e)


def logit(p):
    q = clip(p)
    return math.log(q) - math.log1p(-q)


def swap(vector):
    return tuple(-x if j < 10 else x for j, x in enumerate(vector))


def symmetric(a, b):
    return clip((a + (1. - b)) / 2.)


def _number(value):
    if type(value) not in (int, float) or not math.isfinite(value) or abs(value) > 1e12:
        raise ValueError("invalid bounded logistic parameter")
    return float(value)


@dataclass(frozen=True)
class LogisticParameters:
    mean: tuple[float, ...]
    scale: tuple[float, ...]
    coef: tuple[float, ...]
    intercept: float
    platt_slope: float
    platt_intercept: float

    def _one(self, vector):
        return sigmoid(math.fsum(w * ((x - m) / s)
                                 for w, x, m, s in zip(self.coef, vector, self.mean, self.scale))
                       + self.intercept)

    def raw_probability(self, values):
        v = feature_vector(values)
        return symmetric(self._one(v), self._one(swap(v)))

    def predict(self, values):
        p = self.raw_probability(values)
        return symmetric(sigmoid(self.platt_slope * logit(p) + self.platt_intercept),
                         sigmoid(self.platt_slope * logit(1. - p) + self.platt_intercept))


def parameters_from_payload(payload):
    try:
        if set(payload) != {"mean", "scale", "coef", "intercept", "platt_slope", "platt_intercept"}:
            raise ValueError("unknown parameter fields")
        vectors = []
        for field in ("mean", "scale", "coef"):
            values = payload[field]
            if type(values) not in (tuple, list) or len(values) != len(FEATURE_NAMES):
                raise ValueError("wrong parameter shape")
            vectors.append(tuple(_number(x) for x in values))
        if any(x < 1e-15 for x in vectors[1]):
            raise ValueError("invalid scaler scale")
        return LogisticParameters(*vectors, *(_number(payload[k]) for k in
                                  ("intercept", "platt_slope", "platt_intercept")))
    except (KeyError, TypeError, ValueError, OverflowError):
        raise ValueError("invalid logistic artifact parameters") from None


@dataclass(frozen=True)
class CandidateReceipt:
    model_id: str
    model_digest: str
    config_digest: str
    protocol_id: str
    protocol_digest: str
    dataset_digest: str
    training_cutoff: str
    created_at: str
    fit_n: int
    calibration_n: int

    @property
    def artifact_name(self):
        return self.model_id + ".json"


@dataclass(frozen=True)
class FrozenCandidate:
    receipt: CandidateReceipt
    parameters: LogisticParameters
    protocol: TrainingProtocol
    dataset: TrainingDataset

    def predict(self, values):
        return self.parameters.predict(values)


def _metadata_hashes(values, *, code):
    if type(values) is not dict or not values:
        raise ValueError("invalid provenance manifest")
    for key, value in values.items():
        if type(key) is not str or not key or type(value) is not str or not value:
            raise ValueError("invalid provenance entry")
        if code:
            require_digest(value)
    return _hash(_json(values))


def decode_artifact(raw: str) -> FrozenCandidate:
    """Strict schema and finite numeric validation of inert JSON."""
    if type(raw) is not str or len(raw.encode("utf-8")) > MAX_BYTES:
        raise ValueError("invalid artifact size or encoding")
    try:
        payload = json.loads(raw)
        keys = {"version", "scope", "feature_version", "feature_names", "protocol",
                "protocol_digest", "dataset", "dataset_digest", "config", "config_digest",
                "dependencies", "dependency_digest", "code", "code_digest",
                "training_cutoff", "created_at", "parameters"}
        if (type(payload) is not dict or set(payload) != keys or _json(payload) != raw
                or payload["version"] != ARTIFACT_VERSION or payload["scope"] != "SYNTHETIC"
                or payload["feature_version"] != FEATURE_VERSION
                or payload["feature_names"] != list(FEATURE_NAMES)
                or payload["config"] != fixed_config()
                or payload["config_digest"] != _hash(_json(fixed_config()))):
            raise ValueError("artifact schema or config mismatch")
        p = decode_protocol(payload["protocol"])
        if (payload["protocol"] != protocol_payload(p) or payload["protocol_digest"] != p.digest
                or payload["training_cutoff"] != p.training_cutoff):
            raise ValueError("protocol lineage mismatch")
        data = decode_dataset(payload["dataset"], p)
        if payload["dataset_digest"] != data.digest:
            raise ValueError("dataset digest mismatch")
        created = utc_timestamp(payload["created_at"])
        if created != payload["created_at"] or not p.training_cutoff < created <= p.evaluation_start:
            raise ValueError("invalid freeze clock")
        if (payload["dependency_digest"] != _metadata_hashes(payload["dependencies"], code=False)
                or payload["code_digest"] != _metadata_hashes(payload["code"], code=True)):
            raise ValueError("provenance digest mismatch")
        params = parameters_from_payload(payload["parameters"])
        digest = _hash(raw)
        receipt = CandidateReceipt(MODEL_PREFIX + digest, digest, payload["config_digest"],
            p.protocol_id, p.digest, data.digest, p.training_cutoff, created,
            len(data.fit), len(data.calibration))
        return FrozenCandidate(receipt, params, p, data)
    except (KeyError, TypeError, ValueError, IndexError, OverflowError, RecursionError):
        raise ValueError("invalid canonical synthetic candidate artifact") from None


def _is_reparse(info):
    return bool(getattr(info, "st_file_attributes", 0)
                & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def artifact_directory(root):
    if root is None:
        raise ValueError("explicit local model_artifacts directory required")
    try:
        path = Path(root)
    except TypeError:
        raise ValueError("invalid artifact directory") from None
    if (not path.is_absolute() or ".." in path.parts or path.name != "model_artifacts"
            or (os.name == "nt" and path.anchor.startswith("\\\\"))):
        raise ValueError("use an absolute local model_artifacts directory without traversal")
    for part in reversed((path, *path.parents)):
        info = part.lstat()
        if not stat.S_ISDIR(info.st_mode) or _is_reparse(info):
            raise ValueError("artifact directory contains a link or non-directory")
    return path


def _artifact_path(root, model_id):
    if type(model_id) is not str or not model_id.startswith(MODEL_PREFIX):
        raise ValueError("invalid artifact identity")
    require_digest(model_id[len(MODEL_PREFIX):])
    return artifact_directory(root) / (model_id + ".json")


def read_artifact(root, model_id):
    path = _artifact_path(root, model_id)
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or _is_reparse(before) or before.st_size > MAX_BYTES:
        raise ValueError("artifact must be a bounded regular non-link file")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or not os.path.samestat(before, info):
            raise ValueError("artifact file changed during open")
        content = stream.read(MAX_BYTES + 1)
    after = path.lstat()
    if (len(content) > MAX_BYTES or _is_reparse(after) or not os.path.samestat(info, after)):
        raise ValueError("artifact file changed or exceeds bound")
    try:
        raw = content.decode("utf-8")
    except UnicodeError:
        raise ValueError("artifact must be UTF-8 JSON") from None
    candidate = decode_artifact(raw)
    if candidate.receipt.model_id != model_id:
        raise ValueError("artifact digest mismatch")
    return raw, candidate


def publish_artifact(root, raw):
    candidate = decode_artifact(raw)
    dest = _artifact_path(root, candidate.receipt.model_id)
    if os.path.lexists(dest):
        if read_artifact(root, candidate.receipt.model_id)[0] != raw:
            raise ValueError("conflicting existing artifact")
        return candidate
    fd, name = tempfile.mkstemp(prefix=".s6-candidate-", suffix=".tmp", dir=dest.parent)
    staged = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw.encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        # Same-directory hard link has no replacement fallback.
        try:
            os.link(staged, dest)
        except FileExistsError:
            pass
        if read_artifact(root, candidate.receipt.model_id)[0] != raw:
            raise ValueError("published artifact verification failed")
        return candidate
    finally:
        staged.unlink(missing_ok=True)
