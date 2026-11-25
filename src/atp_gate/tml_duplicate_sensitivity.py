"""Read-only content-pinned duplicate sensitivity for historical research."""
from __future__ import annotations

import csv
import hashlib
import io
import re
from collections import defaultdict

from .tml_historical_audit import TML_COLUMNS

_LEVELS = frozenset({"250", "500", "M", "G"})
_REVIEWED_2024_SHA = "db27fb184b62bc1716ecc84c5a8365088e34e8e9a0101a59782ec7907f6e2de8"
_REVIEWED_2024 = frozenset({"2024-451", "2024-7480"})
_MODES = frozenset({"COLLAPSE_EXACT", "COLLAPSE_EXACT_AND_QUARANTINE_CONFLICT"})


def derive_duplicate_snapshot(data: bytes, *, season: int, expected_sha256: str,
                              expected_exact_groups: int, expected_conflicting_groups: int,
                              mode: str) -> tuple[bytes, dict]:
    """Return temporary derived bytes and aggregate receipt; never certify IDs."""
    if mode not in _MODES:
        raise ValueError("unknown duplicate sensitivity mode")
    if type(season) is not int or not 1968 <= season <= 2026:
        raise ValueError("invalid source season")
    if not isinstance(data, bytes) or not 0 < len(data) <= 20 * 1024 * 1024:
        raise ValueError("invalid source bytes")
    sha = hashlib.sha256(data).hexdigest()
    if expected_sha256 != sha:
        raise ValueError("source SHA256 pin mismatch")
    if any(type(n) is not int or n < 0
           for n in (expected_exact_groups, expected_conflicting_groups)):
        raise ValueError("invalid expected group counts")
    try:
        reader = csv.reader(io.StringIO(data.decode("utf-8-sig"), newline=""), strict=True)
        header = next(reader, None)
        if header != TML_COLUMNS:
            raise ValueError("TML source schema mismatch")
        rows = list(reader)
    except (UnicodeError, csv.Error) as exc:
        raise ValueError("invalid source CSV encoding or syntax") from exc
    col = {name: i for i, name in enumerate(header)}
    def field(row, name):
        return row[col[name]]
    groups = defaultdict(list)
    malformed = 0
    for i, row in enumerate(rows):
        if len(row) != len(header):
            malformed += 1
            continue
        event, w, l, rd = (field(row, k) for k in ("tourney_id", "winner_id", "loser_id", "round"))
        if not all(x.strip() for x in (event, w, l, rd)) or w == l:
            continue
        main = (field(row, "tourney_level") in _LEVELS
                or (season == 2024 and sha == _REVIEWED_2024_SHA
                    and event in _REVIEWED_2024))
        groups[(event, *sorted((w, l)), rd)].append((i, main))
    drop = set()
    exact = conflicts = quarantined = collapsed = outside = 0
    mid = col["match_num"]
    for key, group in groups.items():
        if len(group) < 2:
            continue
        scopes = {main for _, main in group}
        if scopes == {False}:
            outside += 1
            continue
        if len(scopes) != 1:
            raise ValueError("mixed main-tour candidate group")
        indices = [i for i, _ in group]
        nums = [rows[i][mid] for i in indices]
        if (any(not re.fullmatch(r"[1-9][0-9]{0,11}", n) for n in nums)
                or len(set(nums)) != len(nums)):
            raise ValueError("invalid or repeated match number identity in duplicate group")
        # Compare every field except provider match_num, not merely the score.
        logical = {tuple(rows[i][:mid] + rows[i][mid+1:]) for i in indices}
        if len(logical) == 1:
            exact += 1
            keep = min(indices, key=lambda i: int(rows[i][mid]))
            remove = set(indices) - {keep}
            collapsed += len(remove)
            drop.update(remove)
        else:
            conflicts += 1
            if mode == "COLLAPSE_EXACT_AND_QUARANTINE_CONFLICT":
                drop.update(indices)
                quarantined += len(indices)
    if (exact, conflicts) != (expected_exact_groups, expected_conflicting_groups):
        raise ValueError("reviewed duplicate group count drift")
    if drop:
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(header)
        writer.writerows(row for i, row in enumerate(rows) if i not in drop)
        derived = output.getvalue().encode("utf-8")
    else:
        derived = data
    return derived, {
        "schema": "TML_DUPLICATE_SENSITIVITY_V1",
        "mode": mode, "season": season,
        "source_sha256": sha,
        "derived_sha256": hashlib.sha256(derived).hexdigest(),
        "source_rows": len(rows), "derived_rows": len(rows)-len(drop),
        "malformed_rows": malformed, "exact_groups": exact,
        "conflicting_groups": conflicts, "outside_scope_groups": outside,
        "collapsed_rows": collapsed, "quarantined_rows": quarantined,
        "removed_rows": len(drop),
        "official_match_id_verified": False,
        "model_validation_trusted": False, "allocation_enabled": False, "stake": 0,
    }
