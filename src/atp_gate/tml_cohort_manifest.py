"""Immutable research-only cohort definition and local identity diagnostics."""
from __future__ import annotations

import csv
import hashlib
import io
import re
import unicodedata
from collections import defaultdict

from .tml_historical_audit import TML_COLUMNS

_CAP = 20 * 1024 * 1024


def cohort_manifest() -> dict:
    original = {
        2021: "80d570be31d778b143eb58380258243785bf3fcb18db144b42704bc6c56d941b",
        2022: "d70036c6ee6c27dd3deda6e6c9ccd500b66e6e78106fb00794cb277e37353357",
        2023: "9faaf53186ef908b3322d521a8dd2a717401167c0e400a99e1efddb23e13600f",
        2024: "db27fb184b62bc1716ecc84c5a8365088e34e8e9a0101a59782ec7907f6e2de8",
        2025: "5ccf52d912085d6a5ba3effdc5f2f216f170aabfd8850086b5f92c7ccedfd53e",
    }
    return {
        "schema": "TML_RESEARCH_COHORT_MANIFEST_V1",
        "status": "HISTORICAL_SKILL_RESEARCH_ONLY",
        "source_rights_scope": "PERSONAL_NONCOMMERCIAL_RESEARCH",
        "original_sha256": original,
        "derived_sha256": {
            **original,
            2021: "2a2c4a331b1cbae87adace77f4ff5f80e5c60207efd89dd958e6998735c90e92",
            2022: "125a1c0ece4b29ead7ce878b2e1bf844b1737b311fad2bfa873b3503e1cc39f1",
        },
        "original_git_blobs": {
            2021: "2bd4eaf4eb28a09b42ab4ecd5830a8f3ad068faa",
            2022: "2b6726106fefb22b40c2816e4c703a48e9d312be",
            2023: "5ceb7397e3a217e51f197c9e83ea435faf690eeb",
            2024: "cf513429259b4a15e84e2021206895d9bd4ff772",
        },
        "revised_2025_url": "https://stats.tennismylife.org/data/2025.csv",
        "duplicate_mode": "COLLAPSE_EXACT_AND_QUARANTINE_CONFLICT",
        "exact_groups_by_season": {2021:2, 2022:1, 2023:0, 2024:0, 2025:0},
        "conflicting_groups_by_season": {y:0 for y in original},
        "normalize_level_a_2024": True,
        "level_a_registry_sha256": "46a6fd05e2224ad0453480db37a900a495a0a67609ea6a24830fe318f47a3f3b",
        "embargo_days": 28,
        "elo_k": 24,
        "surface_weight": 0.35,
        "expected_eligible": 12620,
        "expected_evaluated": 7694,
        "evaluation_by_year": {2023:2600, 2024:2647, 2025:2447},
        "expected_global_log_loss": 0.6300670180626626,
        "expected_surface_log_loss": 0.6320572443209497,
        "evaluation_status": "PREVIOUSLY_INSPECTED_DEVELOPMENT_YEARS",
        "source_date_semantics": "TOURNAMENT_START_NOT_MATCH_TIME",
        "identity_rule": "EXACT_SOURCE_PLAYER_ID_NO_NAME_BASED_MERGE",
        "official_match_draw_verified": False,
        "individual_match_start_verified": False,
        "source_result_availability_exact": False,
        "participant_known_at_event_start": False,
        "eligible_for_model_training": 0,
        "model_validation_trusted": False,
        "market_edge_verified": False,
        "allocation_enabled": False,
        "stake": 0,
    }


def verify_pinned_inputs(payloads: dict[int, bytes], expected_sha256: dict[int, str]) -> None:
    if (not isinstance(payloads, dict) or not isinstance(expected_sha256, dict)
            or not expected_sha256 or set(payloads) != set(expected_sha256)
            or any(type(y) is not int or not 1968 <= y <= 2026 for y in payloads)
            or any(type(y) is not int for y in expected_sha256)):
        raise ValueError("source season set must match pinned season manifest")
    for year, data in payloads.items():
        pin = expected_sha256[year]
        if (not isinstance(pin, str) or not re.fullmatch(r"[a-f0-9]{64}", pin)
                or not isinstance(data, bytes) or not 0 < len(data) <= _CAP
                or hashlib.sha256(data).hexdigest() != pin):
            raise ValueError("source SHA256 mismatch or invalid source bytes")


def profile_identity_variants(payloads) -> dict:
    """Local review leads only. Do not publish source rows or remap identities."""
    names, ids = defaultdict(set), defaultdict(set)
    malformed = 0
    for data in payloads:
        if not isinstance(data, bytes) or not 0 < len(data) <= _CAP:
            raise ValueError("invalid source bytes")
        try:
            reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline=""), strict=True)
            if reader.fieldnames != TML_COLUMNS:
                raise ValueError("TML source schema mismatch")
            for row in reader:
                if None in row or any(value is None for value in row.values()):
                    malformed += 1
                    continue
                for side in ("winner", "loser"):
                    pid = row[side + "_id"]
                    token = " ".join(unicodedata.normalize("NFC", row[side + "_name"]).casefold().split())
                    if pid.strip() and token:
                        names[pid].add(token)
                        ids[token].add(pid)
        except (UnicodeError, csv.Error) as exc:
            raise ValueError("invalid source CSV encoding or syntax") from exc
    variants = [{"player_id": pid, "name_tokens": sorted(tokens)}
                for pid, tokens in sorted(names.items()) if len(tokens) > 1]
    return {
        "multiple_name_ids": len(variants),
        "multiple_id_names": sum(len(group) > 1 for group in ids.values()),
        "malformed_rows": malformed,
        "variants": variants,
        "identity_remapped": False,
    }
