"""Explicitly opted-in, exact-pinned historical TML ML study; aggregates only."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import tempfile
from importlib.metadata import version

from atp_gate.tml_cohort_manifest import cohort_manifest,verify_pinned_inputs
from atp_gate.tml_duplicate_sensitivity import derive_duplicate_snapshot
from atp_gate.tml_development_data import YEARS,load_development_matches,split_fold
from atp_gate.tml_development_features import FEATURE_NAMES,build_features
from atp_gate.tml_elo_experiment import _elo_p
from atp_gate.tml_skill_scoring import score_skill
from atp_gate.tml_research_ml import verify_research_permission,fit_fold,add_diagnostics
from scripts.p1_8c_cohort_research import acquire_sources

ROOT=Path(__file__).resolve().parents[1]


def run(*,allow_exploratory_fit=False,local_dir=None):
    if allow_exploratory_fit is not True:
        raise ValueError("explicit --allow-exploratory-fit required")
    pb=(ROOT/"docs/registries/p2_1r_tml_development_protocol_v1.json").read_bytes()
    auth=(ROOT/"docs/registries/p2_3_research_permission_v1.json").read_bytes()
    permission=verify_research_permission(auth,pb)
    manifest=cohort_manifest()
    with tempfile.TemporaryDirectory(prefix="p2-3-private-") as temp:
        root=Path(temp)
        raw,_,receipts=acquire_sources(manifest,root,local_dir=local_dir)
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
        selected=[]
        parts_by_year={y:split_fold(rows,y) for y in YEARS}
        for y,parts in parts_by_year.items():
            selected.extend(parts["evaluation"])
        if (len(selected)!=manifest["expected_evaluated"]
                or len({m.key for m in selected})!=len(selected)):
            raise ValueError("locked evaluation key support drift")
        predictions={"coinflip":{m.key:.5 for m in selected},
                     "global_elo":{m.key:_elo_p(features[m.key]["overall_elo_diff"],0.) for m in selected},
                     "surface_elo":{m.key:_elo_p(features[m.key]["surface_shrinkage_elo_diff"],0.) for m in selected}}
        support=[]
        for y,parts in parts_by_year.items():
            support.append({"year":y,**{k:len(v) for k,v in parts.items()}})
            for name in ("logistic","xgboost"):
                for method,pred in fit_fold(parts,features,name).items():
                    dest=predictions.setdefault(name+"_"+method,{})
                    if dest.keys() & pred.keys():
                        raise ValueError("repeated evaluation key across folds")
                    dest.update(pred)
        report=add_diagnostics(score_skill(selected,predictions),selected,predictions)
        for name in ("global","surface"):
            if not math.isclose(report["models"][name+"_elo"]["log_loss"],manifest["expected_"+name+"_log_loss"],abs_tol=1e-12,rel_tol=0):
                raise ValueError("frozen baseline drift")
        return {"schema":"P2_3_FIXED_ML_EVIDENCE_V1","status":"HISTORICAL_SKILL_RESEARCH_ONLY",
                "protocol_sha256":hashlib.sha256(pb).hexdigest(),"permission_sha256":hashlib.sha256(auth).hexdigest(),
                "manifest_sha256":permission["manifest_sha256"],"raw_sha256":manifest["original_sha256"],
                "derived_sha256":manifest["derived_sha256"],
                "acquisition_modes":{y:r["acquisition_mode"] for y,r in receipts.items()},
                "dependencies":{p:version(p) for p in ("numpy","scikit-learn","xgboost","scipy")},
                "fit_support":support,"feature_names":list(FEATURE_NAMES),"evaluation":report,
                "model_fitting_performed":True,"exploratory_fit_scope":permission["scope"],
                "evaluation_status":"PREVIOUSLY_INSPECTED_DEVELOPMENT_YEARS",
                "model_artifact_exported":False,"future_holdout_accessed":False,
                "eligible_for_model_training":0,"official_match_draw_verified":False,
                "model_validation_trusted":False,"allocation_enabled":False,"stake":0}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-exploratory-fit",action="store_true")
    parser.add_argument("--local-dir",type=Path)
    a=parser.parse_args(argv)
    try:
        result=run(allow_exploratory_fit=a.allow_exploratory_fit,local_dir=a.local_dir)
    except (ValueError,OSError,RuntimeError) as exc:
        print(json.dumps({"status":"ERROR","reason":str(exc),"allocation_enabled":False,
                          "model_validation_trusted":False,"stake":0}),flush=True)
        return 2
    print(json.dumps(result,sort_keys=True,allow_nan=False),flush=True)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
