"""Compare two provider revisions without creating IDs or certifying outcomes."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from atp_gate.tml_historical_audit import TML_COLUMNS
from atp_gate.tml_snapshot import update_tml_season
from scripts.reproduce_pinned_tml_elo import PINS, verified_blob

MAX_BYTES = 20 * 1024 * 1024
CORE = ("winner_id", "loser_id", "tourney_date", "tourney_level", "surface", "score")


def _parse(data):
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_BYTES:
        raise ValueError("invalid source bytes")
    reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline=""), strict=True)
    if reader.fieldnames != TML_COLUMNS:
        raise ValueError("source schema changed")
    rows, malformed = [], 0
    for row in reader:
        if None in row or any(v is None for v in row.values()):
            malformed += 1
        else:
            rows.append(row)
    return rows, malformed


def _key(row):
    a, b = row["winner_id"], row["loser_id"]
    if not all(x and x.strip() for x in (row["tourney_id"], row["round"], a, b)) or a == b:
        return None
    return (row["tourney_id"], row["round"], *sorted((a, b)))


def _index(rows):
    candidates = defaultdict(list)
    numbered = Counter()
    for row in rows:
        key = _key(row)
        if key is not None:
            candidates[key].append(row)
        if row["tourney_id"] and row["match_num"].strip():
            numbered[(row["tourney_id"], row["match_num"])] += 1
    return candidates, numbered


def _core_report(groups):
    return {event: {"changed_rows": counts["changed_rows"],
                    "fields": dict(sorted((k, v) for k, v in counts.items()
                                          if k != "changed_rows"))}
            for event, counts in sorted(groups.items())}


def compare_snapshots(old_bytes, current_bytes):
    old, old_bad = _parse(old_bytes)
    current, current_bad = _parse(current_bytes)
    old_index, old_numbers = _index(old)
    new_index, new_numbers = _index(current)
    missing, numbered, changed_fields = Counter(), Counter(), Counter()
    event_repairs = Counter()
    missing_core, numbered_core = defaultdict(Counter), defaultdict(Counter)
    for row in old:
        has_number = bool(row["match_num"].strip())
        disposition = numbered if has_number else missing
        key = _key(row)
        if key is None:
            result = "INVALID_CANDIDATE_IDENTITY"
        elif len(old_index[key]) != 1 or len(new_index.get(key, [])) > 1:
            result = "AMBIGUOUS_IDENTITY"
        elif has_number and old_numbers[(row["tourney_id"], row["match_num"])] != 1:
            result = "DUPLICATE_OLD_MATCH_KEY"
        elif key not in new_index:
            result = "MISSING_IN_CURRENT"
        else:
            candidate = new_index[key][0]
            for col in TML_COLUMNS:
                if col != "match_num" and candidate[col] != row[col]:
                    changed_fields[col] += 1
            core_changes = [c for c in CORE if candidate[c] != row[c]]
            if core_changes:
                result = "CHANGED_CORE"
                event_fields = (numbered_core if has_number else missing_core)[row["tourney_id"]]
                event_fields["changed_rows"] += 1
                event_fields.update(core_changes)
            elif not candidate["match_num"].strip():
                result = "NUMBER_REMOVED" if has_number else "STILL_MISSING"
            elif new_numbers[(candidate["tourney_id"], candidate["match_num"])] != 1:
                result = "DUPLICATE_CURRENT_MATCH_KEY"
            elif has_number:
                result = ("UNCHANGED_NUMBER" if row["match_num"] == candidate["match_num"]
                          else "NUMBER_CHANGED")
            else:
                result = "REPAIRED_CANDIDATE"
                event_repairs[row["tourney_id"]] += 1
        disposition[result] += 1

    return {
        "status": "SOURCE_REVISION_REVIEW_REQUIRED",
        "old_sha256": hashlib.sha256(old_bytes).hexdigest(),
        "current_sha256": hashlib.sha256(current_bytes).hexdigest(),
        "old_raw_rows": len(old) + old_bad,
        "current_raw_rows": len(current) + current_bad,
        "old_malformed_rows": old_bad, "current_malformed_rows": current_bad,
        "old_missing_match_num": sum(missing.values()),
        "current_missing_match_num": sum(not r["match_num"].strip() for r in current),
        "missing_disposition": dict(sorted(missing.items())),
        "numbered_disposition": dict(sorted(numbered.items())),
        "changed_non_number_columns": dict(sorted(changed_fields.items())),
        "repair_candidates_by_event": dict(sorted(event_repairs.items())),
        "missing_core_changes_by_event": _core_report(missing_core),
        "numbered_core_changes_by_event": _core_report(numbered_core),
        "old_ambiguous_candidate_groups": sum(len(v)>1 for v in old_index.values()),
        "current_ambiguous_candidate_groups": sum(len(v)>1 for v in new_index.values()),
        "current_duplicate_number_groups": sum(v>1 for v in new_numbers.values()),
        "new_unique_candidate_keys_absent_from_old": sum(
            len(v)==1 and k not in old_index for k,v in new_index.items()),
        "official_match_draw_verified": False,
        "eligible_for_model_training": 0,
        "model_validation_trusted": False,
        "allocation_enabled": False, "stake": 0,
    }


def main():
    old = verified_blob(PINS[2025])
    with tempfile.TemporaryDirectory(prefix="tml-revision-research-") as root:
        update = update_tml_season(2025, Path(root), at=datetime.now(timezone.utc))
        current = Path(update["local_snapshot"]).read_bytes()
        if hashlib.sha256(current).hexdigest() != "5ccf52d912085d6a5ba3effdc5f2f216f170aabfd8850086b5f92c7ccedfd53e":
            raise ValueError("publisher revision changed since first research run; preserve prior evidence")
        report = compare_snapshots(old, current)
        if report["old_missing_match_num"] != 489:
            raise ValueError("pinned missing-row count differs")
        print(json.dumps({
            "old_source": {"provider": "TennisMyLife GitHub archive",
                           "git_blob_sha1": PINS[2025]},
            "current_source": {"url": update["source_url"], "checked_at_utc": update["checked_at_utc"]},
            "revision_audit": report,
        }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
