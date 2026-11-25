"""P1.8b: run exact-clone and conflicting-group sensitivity on pinned sources."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import tempfile

from atp_gate.tml_duplicate_sensitivity import derive_duplicate_snapshot
from atp_gate.tml_elo_experiment import _load, _score, run_tml_elo_experiment
from atp_gate.tml_snapshot import update_tml_season
from scripts.reproduce_pinned_tml_elo import PINS, verified_blob
from scripts.p1_7c_level_a_research import SHA256, NEW_SHA, YEARS, predictions

MODES = ("COLLAPSE_EXACT", "COLLAPSE_EXACT_AND_QUARANTINE_CONFLICT")
EXPECTED_EXACT = {2021: 2, 2022: 1, 2023: 0, 2024: 0, 2025: 0}


def evaluate(paths):
    report = run_tml_elo_experiment(paths, normalize_level_a_2024=True,
                                    bootstrap_replicates=50)
    if (report["allocation_enabled"] or report["stake"] != 0
            or report["model_validation_trusted"] or report["market_edge_verified"]):
        raise ValueError("research boundary violated")
    matches, _, _, _, _ = _load(paths, normalize_level_a_2024=True)
    evaluation = sorted((m for m in matches if m.start.year in YEARS),
                        key=lambda m: m.start)
    rows = predictions(matches)
    if len(evaluation) != len(rows):
        raise ValueError("evaluation identity alignment mismatch")
    observed = _score(rows)
    for k, v in report["aggregate"].items():
        if not math.isclose(observed[k], v, rel_tol=0, abs_tol=1e-12):
            raise ValueError("diagnostic replay disagrees with baseline")
    # Same pre-event state implies identical _Match records have identical
    # predicted probabilities; only their multiplicity may differ.
    lookup = {}
    for m, r in zip(evaluation, rows):
        if (m.event_id, m.outcome_a) != r[:2]:
            raise ValueError("prediction alignment mismatch")
        if m in lookup and lookup[m] != r:
            raise ValueError("identical logical records predicted differently")
        lookup[m] = r
    return report, matches, evaluation, lookup


def compare(paths, pins, label, expected_n, expected_eligible, root):
    base, bm, be, bp = evaluate(paths)
    if (base["test_matches"], base["source_match_rows_eligible"]) != (expected_n, expected_eligible):
        raise ValueError("locked baseline count drift")
    scenarios = []
    for mode in MODES:
        local = root / (label + "_" + mode)
        local.mkdir()
        derived_paths, receipts = [], []
        for year, original in zip(sorted(pins), paths):
            conflict = int(year == 2025 and label == "ORIGINAL_PINNED")
            raw = original.read_bytes()
            derived, receipt = derive_duplicate_snapshot(
                raw, season=year, expected_sha256=pins[year],
                expected_exact_groups=EXPECTED_EXACT[year],
                expected_conflicting_groups=conflict, mode=mode)
            path = local / f"{year}-{receipt['derived_sha256']}.csv"
            path.write_bytes(derived)
            derived_paths.append(path)
            receipts.append(receipt)
        report, mm, ee, pp = evaluate(derived_paths)
        if Counter(mm) - Counter(bm) or Counter(ee) - Counter(be):
            raise ValueError("derived cohort contains new or modified match records")
        removed = sum(r["removed_rows"] for r in receipts)
        expected_removed = 3 + (2 if mode == MODES[1] and label == "ORIGINAL_PINNED" else 0)
        if removed != expected_removed or len(bm) - len(mm) != removed:
            raise ValueError("eligible removal reconciliation failed")
        if len(be) - len(ee) != expected_removed - 3:
            raise ValueError("evaluation removal reconciliation failed")
        # Use the retained logical-record multiset for the matched comparison.
        matched_before = _score([bp[m] for m in ee])
        matched_after = _score([pp[m] for m in ee])
        scenarios.append({
            "mode": mode, "receipts": receipts,
            "eligible": report["source_match_rows_eligible"],
            "folds": report["folds"], "aggregate": report["aggregate"],
            "matched_cohort": {"before": matched_before, "after": matched_after},
            "removed_eligible": removed, "removed_evaluation": len(be)-len(ee),
        })
    return {
        "schema": "TML_PINNED_DUPLICATE_SENSITIVITY_V1",
        "status": "HISTORICAL_SKILL_RESEARCH_ONLY",
        "variant": label, "source_pins": pins,
        "baseline": {"eligible": base["source_match_rows_eligible"],
                     "folds": base["folds"], "aggregate": base["aggregate"]},
        "scenarios": scenarios,
        "official_match_id_verified": False, "official_match_draw_verified": False,
        "model_validation_trusted": False, "market_edge_verified": False,
        "allocation_enabled": False, "stake": 0,
    }


def main():
    with tempfile.TemporaryDirectory(prefix="tml-duplicate-sensitivity-") as folder:
        root = Path(folder)
        paths = []
        for year, blob in sorted(PINS.items()):
            raw = verified_blob(blob)
            if hashlib.sha256(raw).hexdigest() != SHA256[year]:
                raise ValueError("original SHA drift")
            path = root / f"{year}-{SHA256[year]}.csv"
            path.write_bytes(raw)
            paths.append(path)
        print(json.dumps(compare(paths, SHA256, "ORIGINAL_PINNED", 7247, 12176, root),
                         sort_keys=True), flush=True)
        receipt = update_tml_season(2025, root, at=datetime.now(timezone.utc))
        revised = Path(receipt["local_snapshot"])
        print(json.dumps(compare(paths[:4]+[revised], {**SHA256, 2025: NEW_SHA},
                                 "REVISED_2025_PINNED", 7694, 12623, root),
                         sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
