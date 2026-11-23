"""Re-run a historical study against its saved report, fail-closed.

This establishes repeatability under the same code, packages, input bytes and
training parameters. It does NOT validate odds timestamps or market edge.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Sequence

from .research_train import _execution_environment, run_research


def _sha256_and_size(path: Path) -> tuple[str, int]:
    h = hashlib.sha256()
    n = 0
    with path.open("rb") as handle:
        for piece in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(piece)
            n += len(piece)
    return h.hexdigest(), n


def _reject_result() -> dict:
    return {
        "status": "REJECT",
        "mode": "HISTORICAL_RESEARCH_ONLY",
        "matching_sources": 0,
        "reasons": [],
        "scope": "RESEARCH_REPLAY_ONLY",
        "live_eligible": False,
        "allocation_enabled": False,
        "validation_report_trusted": False,
        "stake": 0,
    }


def replay_saved_report(report_path: str | Path,
                        sources: Sequence[str | Path]) -> dict:
    """Compare saved experiment with a rerun only after provenance checks pass."""
    result = _reject_result()
    reasons = result["reasons"]
    try:
        stored = json.loads(Path(report_path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        reasons.append("INVALID_REPORT")
        return result
    if not isinstance(stored, dict):
        reasons.append("INVALID_REPORT")
        return result

    if (stored.get("mode") != "HISTORICAL_RESEARCH_ONLY"
            or stored.get("live_eligible") is not False
            or stored.get("allocation_enabled") is not False
            or stored.get("validation_report_trusted") is not False
            or type(stored.get("stake")) not in (int, float)
            or stored.get("stake") != 0):
        reasons.append("UNSAFE_REPORT")
        return result

    environment = stored.get("execution_environment")
    if (not isinstance(environment, dict)
            or not isinstance(environment.get("packages"), dict)
            or not isinstance(environment.get("code_sha256"), str)):
        reasons.append("ENVIRONMENT_NOT_RECORDED")
        return result
    if environment != _execution_environment():
        reasons.append("ENVIRONMENT_MISMATCH")
        return result

    configuration = stored.get("training_configuration")
    required = ("minimum_total", "minimum_target", "random_state")
    if (not isinstance(configuration, dict)
            or any(type(configuration.get(key)) is not int or configuration[key] < 1
                   for key in required)):
        reasons.append("REPLAY_PARAMETERS_MISSING")
        return result

    audit = stored.get("data_audit")
    manifest = audit.get("source_files") if isinstance(audit, dict) else None
    if not isinstance(manifest, list) or not manifest:
        reasons.append("INVALID_SOURCE_MANIFEST")
        return result
    saved_names: list[str] = []
    for record in manifest:
        if not isinstance(record, dict):
            reasons.append("INVALID_SOURCE_MANIFEST")
            return result
        name = record.get("name")
        sha = record.get("sha256")
        size = record.get("size_bytes")
        if (not isinstance(name, str) or not name or Path(name).name != name
                or not isinstance(sha, str) or not re.fullmatch(r"[a-f0-9]{64}", sha)
                or type(size) is not int or size < 0):
            reasons.append("INVALID_SOURCE_MANIFEST")
            return result
        saved_names.append(name)
    if len(saved_names) != len(set(saved_names)):
        reasons.append("DUPLICATE_SOURCE_NAME")
        return result

    files = [Path(source) for source in sources]
    if [path.name for path in files] != saved_names:
        reasons.append("SOURCE_SET_OR_ORDER_MISMATCH")
        return result

    for record, path in zip(manifest, files):
        try:
            digest, size = _sha256_and_size(path)
        except OSError:
            reasons.append("SOURCE_UNREADABLE")
            return result
        if digest != record["sha256"] or size != record["size_bytes"]:
            reasons.append("SOURCE_CONTENT_MISMATCH")
            return result

    result["matching_sources"] = len(files)
    try:
        fresh = run_research(
            files, minimum_total=configuration["minimum_total"],
            minimum_target=configuration["minimum_target"],
            seed=configuration["random_state"],
        )
    except (OSError, ValueError, RuntimeError, KeyError, TypeError):
        reasons.append("REPLAY_FAILED")
        return result
    if fresh != stored:
        reasons.append("METRICS_OR_CONFIG_MISMATCH")
        return result

    result["status"] = "REPRODUCED"
    return result
