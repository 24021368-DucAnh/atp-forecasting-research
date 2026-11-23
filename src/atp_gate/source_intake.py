"""Strict, local, historical correction-source intake. No model-use authorization.

An independently accepted rights-review report and source byte provenance are
necessary but NOT sufficient to certify match outcomes, draw completeness,
T-minus-60 prices, calibration, or betting profitability.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Mapping
from urllib.parse import urlsplit

VERSION = "P1_AUTHORIZED_SOURCE_INTAKE_1"
SHA_PATTERN = re.compile(r"^[0-9a-f]{64}$")
ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{2,127}$")
LEGACY_ARCHIVE = "https://www.valuebetennis.com/tournaments/2024/02/archive.htm"


def _record(record: object, fields: set[str], name: str) -> dict:
    if not isinstance(record, dict) or set(record) != fields:
        raise ValueError(f"invalid {name} fields")
    return record


def _sha(value: object, name: str) -> str:
    if not isinstance(value, str) or not SHA_PATTERN.fullmatch(value):
        raise ValueError(f"invalid {name} SHA256")
    return value


def _url(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"invalid {name} URL")
    parts = urlsplit(value)
    if (parts.scheme != "https" or not parts.hostname or parts.username
            or parts.password or parts.fragment):
        raise ValueError(f"invalid {name} HTTPS URL")
    return value


def _id(value: object, name: str) -> str:
    if not isinstance(value, str) or not ID_PATTERN.fullmatch(value):
        raise ValueError(f"invalid {name} report identifier")
    return value


def _claimed_time(value: object, as_of: datetime) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError("invalid retrieval timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid retrieval timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(None):
        raise ValueError("retrieved_at_utc must be UTC")
    if parsed > as_of:
        raise ValueError("source retrieval timestamp is future to as-of")
    return parsed


def _artifact_digest(path: Path) -> tuple[int, str]:
    hasher = hashlib.sha256()
    size = 0
    try:
        with path.open("rb") as f:
            for block in iter(lambda: f.read(1024 * 1024), b""):
                hasher.update(block)
                size += len(block)
    except OSError as exc:
        raise ValueError("source artifact unreadable") from exc
    return size, hasher.hexdigest()


def audit_source_intake(
    artifact_path: Path,
    manifest: dict,
    *,
    inventory_sha256: str,
    allowed_event_keys: set[str],
    as_of: datetime,
    trusted_permission_reports: Mapping[str, str] | None = None,
) -> dict:
    """Check source bytes and independent permission-receipt identity.

    Never sets training readiness or proves rights solely from a manifest.
    Neither draw review flags nor HTML index IDs are match-level certification.
    """
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("audit as-of must be timezone-aware")
    artifact_path = Path(artifact_path)
    m = _record(manifest, {
        "version", "inventory_sha256", "source", "scope_event_keys",
        "permission", "draw_review",
    }, "intake manifest")
    if m["version"] != VERSION:
        raise ValueError("unknown intake version")
    if _sha(m["inventory_sha256"], "manifest inventory") != _sha(inventory_sha256, "expected inventory"):
        raise ValueError("pinned inventory digest mismatch")

    source = _record(m["source"], {
        "name", "sha256", "size_bytes", "source_url",
        "retrieved_at_utc", "format", "row_count_claimed",
    }, "source")
    name = source["name"]
    if (not isinstance(name, str) or not name or Path(name).name != name
            or name in (".", "..") or not name.casefold().endswith(".csv")
            or artifact_path.name != name):
        raise ValueError("source artifact basename is not pinned")
    if source["format"] != "CSV":
        raise ValueError("only correction CSV artifact is supported")
    if type(source["size_bytes"]) is not int or source["size_bytes"] <= 0:
        raise ValueError("source artifact size must be positive integer")
    if type(source["row_count_claimed"]) is not int or source["row_count_claimed"] <= 0:
        raise ValueError("source row-count claim must be positive integer")
    expected_sha = _sha(source["sha256"], "source")
    source_url = _url(source["source_url"], "source")
    if source_url.rstrip("/") == LEGACY_ARCHIVE or source_url.endswith("/archive.htm"):
        raise ValueError("legacy HTML tournament index is not a match correction artifact")
    retrieved = _claimed_time(source["retrieved_at_utc"], as_of)

    scope = m["scope_event_keys"]
    if (not isinstance(scope, list) or not scope or
            any(not isinstance(x, str) for x in scope) or
            len(set(scope)) != len(scope) or not set(scope).issubset(allowed_event_keys)):
        raise ValueError("unverified or duplicate official event scope")

    permission = _record(m["permission"], {
        "scope", "evidence_url", "report_id", "report_sha256",
        "ai_training_allowed", "commercial_use_allowed",
    }, "source permission")
    if permission["scope"] != "2024_FEB_MATCH_LEVEL_EXPORT":
        raise ValueError("permission scope must identify February 2024 match-level export")
    _url(permission["evidence_url"], "permission evidence")
    rid = _id(permission["report_id"], "permission")
    report_hash = _sha(permission["report_sha256"], "permission report")
    if type(permission["ai_training_allowed"]) is not bool or type(permission["commercial_use_allowed"]) is not bool:
        raise ValueError("permission assertions must be actual booleans")

    review = _record(m["draw_review"], {
        "report_id", "report_sha256", "verified_official_match_ids", "complete_main_draw",
    }, "draw review")
    _id(review["report_id"], "draw review")
    _sha(review["report_sha256"], "draw review")
    if type(review["verified_official_match_ids"]) is not bool or type(review["complete_main_draw"]) is not bool:
        raise ValueError("draw review assertions must be actual booleans")

    size, actual_sha = _artifact_digest(artifact_path)
    if size != source["size_bytes"]:
        raise ValueError("source size does not match pinned artifact")
    if actual_sha != expected_sha:
        raise ValueError("source SHA256 does not match pinned artifact")

    trusted = trusted_permission_reports or {}
    rights_reviewed = (
        trusted.get(rid) == report_hash
        and permission["ai_training_allowed"] is True
        and permission["commercial_use_allowed"] is True
    )
    return {
        "status": (
            "SOURCE_PERMISSION_REVIEWED_MATCH_AUDIT_PENDING"
            if rights_reviewed else "NO_AUTHORIZED_HISTORICAL_REPAIR_SOURCE"
        ),
        "mode": "HISTORICAL_RESEARCH_ONLY",
        "intake_version": VERSION,
        "inventory_sha256": inventory_sha256,
        "source_sha256": actual_sha,
        "source_size_bytes": size,
        "retrieved_at_utc": retrieved.isoformat(),
        "scope_event_keys": sorted(scope),
        "claimed_row_count_unverified": source["row_count_claimed"],
        "rights_reviewed": rights_reviewed,
        "main_draw_verified": False,
        "event_identity_verified": False,
        "license_scope_verified_for_model_training": rights_reviewed,
        "historical_match_outcomes_verified": False,
        "t60_quote_verified": False,
        "eligible_for_model_training": 0,
        "live_eligible": False,
        "allocation_enabled": False,
        "validation_report_trusted": False,
        "stake": 0,
        "warnings": (
            ["HISTORICAL_MATCH_DRAW_RECONCILIATION_REQUIRED",
             "NO_TRUSTED_T60_PRICE_SNAPSHOTS",
             "PERMISSION_RECEIPT_NOT_LEGAL_OR_DATA_CERTIFICATION"]
            if rights_reviewed
            else ["NO_INDEPENDENT_PERMISSION_RECEIPT", "SOURCE_QUARANTINED",
                  "HISTORICAL_MATCH_DRAW_RECONCILIATION_REQUIRED"]
        ),
    }
