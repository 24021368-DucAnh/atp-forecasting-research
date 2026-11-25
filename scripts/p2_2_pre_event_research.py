"""Actual-source P2.2a–d research pipeline check; no fitting or raw output."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import random
import tempfile

from atp_gate.tml_cohort_manifest import cohort_manifest,verify_pinned_inputs
from atp_gate.tml_duplicate_sensitivity import derive_duplicate_snapshot
from atp_gate.tml_development_data import YEARS,load_development_matches,split_fold
from atp_gate.tml_development_features import FEATURE_NAMES,build_features,swap_features
from atp_gate.tml_elo_experiment import _elo_p
from atp_gate.tml_skill_scoring import score_skill
from scripts.p1_8c_cohort_research import acquire_sources

ROOT=Path(__file__).resolve().parents[1]


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-dir",type=Path)
    args=parser.parse_args(argv)
    manifest=cohort_manifest()
    protocol_bytes=(ROOT/"docs/registries/p2_1r_tml_development_protocol_v1.json").read_bytes()
    protocol=json.loads(protocol_bytes)
    if tuple(protocol["features"]["allowlist"])!=FEATURE_NAMES:
        raise ValueError("registered feature schema drift")
    with tempfile.TemporaryDirectory(prefix="p2-2-") as temp:
        root=Path(temp)
        raw,_,receipts=acquire_sources(manifest,root,local_dir=args.local_dir)
        derived={}
        for year,data in sorted(raw.items()):
            derived[year],_=derive_duplicate_snapshot(data,season=year,
                expected_sha256=manifest["original_sha256"][year],
                expected_exact_groups=manifest["exact_groups_by_season"][year],
                expected_conflicting_groups=manifest["conflicting_groups_by_season"][year],
                mode=manifest["duplicate_mode"])
        verify_pinned_inputs(derived,manifest["derived_sha256"])
        paths=[]
        for year,data in sorted(derived.items()):
            p=root/f"{year}-{manifest['derived_sha256'][year]}.csv"
            p.write_bytes(data);paths.append(p)
        rows=load_development_matches(paths,locked=True)
        features=build_features(rows)
        shuffled=rows.copy();random.Random(29).shuffle(shuffled)
        if features!=build_features(shuffled) or len(features)!=len(rows):
            raise ValueError("feature determinism or coverage drift")
        for f in features.values():
            if swap_features(swap_features(f))!=f:
                raise ValueError("feature orientation roundtrip failed")
        folds=[]
        selected=[]
        for year in YEARS:
            parts=split_fold(rows,year)
            selected.extend(parts["evaluation"])
            folds.append({"year":year,"partitions":{name:{"n":len(group),
                "event_clusters":len({m.event_id for m in group})} for name,group in parts.items()}})
        if len(selected)!=manifest["expected_evaluated"]:
            raise ValueError("evaluation support drift")
        preds={"coinflip":{m.key:.5 for m in selected},
               "global_elo":{m.key:_elo_p(features[m.key]["overall_elo_diff"],0.) for m in selected},
               "surface_elo":{m.key:_elo_p(features[m.key]["surface_shrinkage_elo_diff"],0.) for m in selected}}
        report=score_skill(selected,preds)
        for name in ("global","surface"):
            if not math.isclose(report["models"][name+"_elo"]["log_loss"],manifest["expected_"+name+"_log_loss"],abs_tol=1e-12,rel_tol=0):
                raise ValueError("frozen Elo score drift")
        # Aggregate-only audit; no keys, rows, labels, or features printed.
        print(json.dumps({"schema":"P2_2_PRE_EVENT_EVIDENCE_V1",
            "protocol_sha256":hashlib.sha256(protocol_bytes).hexdigest(),
            "manifest_sha256":hashlib.sha256(json.dumps(manifest,sort_keys=True,separators=(",",":")).encode()).hexdigest(),
            "raw_sha256":manifest["original_sha256"],"derived_sha256":manifest["derived_sha256"],
            "eligible":len(rows),"unique_match_keys":len({m.key for m in rows}),
            "features":list(FEATURE_NAMES),"feature_rows":len(features),
            "deterministic_shuffled_input":True,"orientation_roundtrip":True,"folds":folds,
            "evaluation":report,"cold_start_evaluation_rows":sum(not features[m.key]["both_have_history"] for m in selected),
            "model_fitting_performed":False,"eligible_for_model_training":0,
            "official_match_draw_verified":False,"model_validation_trusted":False,"allocation_enabled":False,"stake":0},
            sort_keys=True),flush=True)


if __name__=="__main__":
    main()
