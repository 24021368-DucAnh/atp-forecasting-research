"""Compare parser repair with the immutable P1.8c implementation on identical pins."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from atp_gate import tml_elo_experiment as current
from atp_gate.tml_cohort_manifest import cohort_manifest, verify_pinned_inputs
from atp_gate.tml_duplicate_sensitivity import derive_duplicate_snapshot
from atp_gate.tml_snapshot import update_tml_season
from scripts.reproduce_pinned_tml_elo import verified_blob
from scripts.p1_7c_level_a_research import predictions

BASE = "2e084eedfc44c8ffaabd1fc5cbfb00769b703574"
BASE_BLOB = "0a259b21cbf287f292015a4aa1878303c02ea6e9"


def legacy_module(root):
    data = subprocess.check_output(["git", "show", BASE + ":src/atp_gate/tml_elo_experiment.py"])
    if hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest() != BASE_BLOB:
        raise ValueError("frozen baseline module mismatch")
    path = root / "legacy_elo.py"
    path.write_bytes(data)
    name = "atp_gate._p1_8c_frozen_elo"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def key(m):
    return (m.event_id, m.start, m.surface, m.player_a, m.player_b, m.outcome_a)


def predict_map(matches):
    selected = sorted((m for m in matches if m.start.year in (2023,2024,2025)),
                      key=lambda m: m.start)
    rows = predictions(matches)
    if len(selected) != len(rows):
        raise ValueError("prediction count drift")
    mapping = {}
    for m, r in zip(selected, rows):
        if (m.event_id, m.outcome_a) != r[:2]:
            raise ValueError("prediction alignment mismatch")
        k = key(m)
        if k in mapping and mapping[k] != r:
            raise ValueError("ambiguous identical match projections")
        mapping[k] = r
    return selected, mapping


def main():
    m = cohort_manifest()
    with tempfile.TemporaryDirectory(prefix="p1-9b-parser-impact-") as tmp:
        root = Path(tmp)
        legacy = legacy_module(root)
        raw = {y:verified_blob(pin) for y,pin in m["original_git_blobs"].items()}
        r = update_tml_season(2025, root, at=datetime.now(timezone.utc))
        raw[2025] = Path(r["local_snapshot"]).read_bytes()
        verify_pinned_inputs(raw, m["original_sha256"])
        derived = {}
        for y, data in sorted(raw.items()):
            derived[y], _ = derive_duplicate_snapshot(
                data, season=y, expected_sha256=m["original_sha256"][y],
                expected_exact_groups=m["exact_groups_by_season"][y],
                expected_conflicting_groups=m["conflicting_groups_by_season"][y],
                mode=m["duplicate_mode"])
        verify_pinned_inputs(derived, m["derived_sha256"])
        paths = []
        for y, data in sorted(derived.items()):
            p = root / f"{y}-{m['derived_sha256'][y]}.csv"
            p.write_bytes(data)
            paths.append(p)
        old = legacy.run_tml_elo_experiment(paths, normalize_level_a_2024=True,
                                            bootstrap_replicates=50)
        new = current.run_tml_elo_experiment(paths, normalize_level_a_2024=True,
                                            bootstrap_replicates=50)
        if old["source_match_rows_eligible"] != m["expected_eligible"] or old["test_matches"] != m["expected_evaluated"]:
            raise ValueError("frozen baseline count drift")
        if abs(old["aggregate"]["global_elo_log_loss"]-m["expected_global_log_loss"]) > 1e-12:
            raise ValueError("frozen baseline metric drift")
        before, _, _, _, _ = legacy._load(paths, normalize_level_a_2024=True)
        after, _, _, _, _ = current._load(paths, normalize_level_a_2024=True)
        bc, ac = Counter(map(key,before)), Counter(map(key,after))
        removed, added = bc-ac, ac-bc
        be, bp = predict_map(before)
        ae, ap = predict_map(after)
        common = Counter(map(key,be)) & Counter(map(key,ae))
        matched = list(common.elements())
        if not matched:
            raise ValueError("no matched evaluation records")
        def summary(report):
            if report["allocation_enabled"] or report["model_validation_trusted"] or report["stake"] != 0:
                raise ValueError("research boundary violated")
            return {k: report[k] for k in ("source_match_rows_eligible","test_matches","folds","aggregate","excluded_reasons")}
        print(json.dumps({
            "schema":"P1_9B_PARSER_IMPACT_V1","baseline_commit":BASE,
            "baseline_blob":BASE_BLOB,"source_pins":m["original_sha256"],
            "derived_pins":m["derived_sha256"],"baseline":summary(old),"candidate":summary(new),
            "removed_projection_count":sum(removed.values()),"added_projection_count":sum(added.values()),
            "removed_by_event_start_year":dict(Counter(k[1].year for k,n in removed.items() for _ in range(n))),
            "added_by_event_start_year":dict(Counter(k[1].year for k,n in added.items() for _ in range(n))),
            "matched_evaluation":{"n":len(matched),"baseline":current._score([bp[k] for k in matched]),
                                  "candidate":current._score([ap[k] for k in matched])},
            "score_policy":"STANDARD_SET_TOKEN_SYNTAX_NOT_OFFICIAL_COMPLETION",
            "status":"HISTORICAL_SKILL_RESEARCH_ONLY","official_match_draw_verified":False,
            "model_validation_trusted":False,"allocation_enabled":False,"stake":0
        },sort_keys=True),flush=True)


if __name__ == "__main__":
    main()
