"""Verify historical research report inputs; never certify model performance.

This checks provenance hashes and basic report safety/chronology only.
It does NOT rerun training, validate outcomes, or authorize allocations.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Sequence


def _digest(path: Path) -> tuple[int, str]:
    hash_value = hashlib.sha256()
    size = 0
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            size += len(chunk)
            hash_value.update(chunk)
    return size, hash_value.hexdigest()


def _valid_splits(splits: object) -> bool:
    if not isinstance(splits, dict):
        return False
    names = ('train_end', 'calibrate_start', 'calibrate_end', 'holdout_start')
    try:
        values = []
        for name in names:
            raw = splits[name]
            if not isinstance(raw, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', raw):
                return False
            values.append(date.fromisoformat(raw))
        return values[0] < values[1] <= values[2] < values[3]
    except (KeyError, TypeError, ValueError):
        return False


def verify_research_report(report_path: Path, source_paths: Sequence[Path]) -> dict:
    """Compare original input bytes against the audit manifest in a research report.

    All error conditions reject without raising, and output never grants live trust.
    Report integrity is NOT equivalent to model replication or model validation.
    """
    reasons: list[str] = []
    verified = 0
    result = {
        'status': 'REJECT', 'mode': 'HISTORICAL_RESEARCH_ONLY',
        'source_files_verified': 0, 'reasons': reasons,
        'live_eligible': False, 'allocation_enabled': False,
        'validation_report_trusted': False, 'stake': 0,
        'scope': 'INPUT_BYTES_AND_REPORT_SAFETY_ONLY',
    }
    try:
        report = json.loads(Path(report_path).read_text(encoding='utf-8'))
    except (OSError, UnicodeError, ValueError):
        reasons.append('INVALID_REPORT')
        return result
    if not isinstance(report, dict):
        reasons.append('INVALID_REPORT')
        return result

    if (report.get('mode') != 'HISTORICAL_RESEARCH_ONLY'
            or report.get('live_eligible') is not False
            or report.get('allocation_enabled') is not False
            or report.get('validation_report_trusted') is not False
            or type(report.get('stake')) not in (int, float)
            or report.get('stake') != 0):
        reasons.append('UNSAFE_REPORT')
    if not _valid_splits(report.get('splits')):
        reasons.append('INVALID_TEMPORAL_SPLIT')

    audit = report.get('data_audit')
    manifest = audit.get('source_files') if isinstance(audit, dict) else None
    if not isinstance(manifest, list) or not manifest:
        reasons.append('INVALID_SOURCE_MANIFEST')
        return result
    expected: dict[str, tuple[int, str]] = {}
    for entry in manifest:
        if not isinstance(entry, dict):
            reasons.append('INVALID_SOURCE_MANIFEST')
            return result
        name, sha, size = entry.get('name'), entry.get('sha256'), entry.get('size_bytes')
        if (not isinstance(name, str) or not name or Path(name).name != name
                or not isinstance(sha, str) or not re.fullmatch(r'[a-f0-9]{64}', sha)
                or type(size) is not int or size < 0):
            reasons.append('INVALID_SOURCE_MANIFEST')
            return result
        if name in expected:
            reasons.append('DUPLICATE_SOURCE_NAME')
        expected[name] = (size, sha)

    actual: dict[str, Path] = {}
    for source in source_paths:
        source = Path(source)
        if source.name in actual:
            reasons.append('DUPLICATE_SOURCE_NAME')
        actual[source.name] = source
    if set(expected) != set(actual):
        reasons.append('SOURCE_SET_MISMATCH')

    for name in sorted(set(expected) & set(actual)):
        try:
            size, sha = _digest(actual[name])
        except OSError:
            reasons.append('SOURCE_UNREADABLE')
            continue
        if size != expected[name][0]:
            reasons.append('SOURCE_SIZE_MISMATCH')
        if sha != expected[name][1]:
            reasons.append('SOURCE_HASH_MISMATCH')
        if (size, sha) == expected[name]:
            verified += 1

    result['source_files_verified'] = verified
    result['reasons'] = sorted(set(reasons))
    if not reasons:
        result['status'] = 'MATCH'
    return result
