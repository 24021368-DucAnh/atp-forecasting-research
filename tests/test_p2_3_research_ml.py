"""P2.3 synthetic tests; no provider rows."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from atp_gate.tml_research_ml import (verify_research_permission, fit_fold,
    calibration_diagnostics, symmetric_probability)
from atp_gate.tml_development_features import build_features, FEATURE_NAMES
from test_p2_2_pre_event_skill import m

ROOT=Path(__file__).resolve().parents[1]
PROTOCOL=(ROOT/"docs/registries/p2_1r_tml_development_protocol_v1.json").read_bytes()
PERMISSION=(ROOT/"docs/registries/p2_3_research_permission_v1.json").read_bytes()


def test_permission_deny_by_default_and_pin_drift():
    for payload in (None,b"{}",PERMISSION+b" "):
        with pytest.raises(ValueError):
            verify_research_permission(payload,PROTOCOL)
    with pytest.raises(ValueError):
        verify_research_permission(PERMISSION,PROTOCOL+b" ")
    result=verify_research_permission(PERMISSION,PROTOCOL)
    assert result["scope"]=="PRIVATE_NONCOMMERCIAL_LOCKED_TML_DEVELOPMENT_ONLY"
    assert result["eligible_for_model_training"]==0
    assert result["allocation_enabled"] is False


def test_symmetric_probability_complements():
    a=np.array([.8,.3,.9]); b=np.array([.4,.9,.2])
    p=symmetric_probability(a,b)
    assert np.allclose(p,[.7,.2,.85])
    assert np.allclose(p+symmetric_probability(b,a),1)


def fixture():
    rows=[]
    for name,month in (("fit","2022-03"),("cal","2022-09"),("eval","2023-03")):
        for i in range(1,13):
            rows.append(m(name+str(i),1,month+"-"+str(i).zfill(2),
                a="A" if i%3 else "B", b="Z", y=int(i%2==0)))
    return rows


@pytest.mark.parametrize("model",["logistic","xgboost"])
def test_fit_frozen_prediction_invariant_to_evaluation_labels(model):
    rows=fixture()
    parts={"fit":rows[:12],"calibration":rows[12:24],"evaluation":rows[24:]}
    f=build_features(rows)
    a=fit_fold(parts,f,model)
    changed={**parts,"evaluation":[replace(r,outcome_a=1-r.outcome_a) for r in parts["evaluation"]]}
    b=fit_fold(changed,f,model)
    assert a==b
    assert set(a)=={"raw","platt","isotonic"}
    for pred in a.values():
        assert set(pred)=={r.key for r in parts["evaluation"]}
        assert all(0<p<1 for p in pred.values())


def test_partition_overlap_and_feature_mismatch_fail():
    rows=fixture()
    f=build_features(rows)
    parts={"fit":rows[:12],"calibration":rows[12:24],"evaluation":rows[24:]}
    with pytest.raises(ValueError):
        fit_fold({**parts,"calibration":parts["fit"]},f,"logistic")
    bad={k:dict(v) for k,v in f.items()}
    bad[rows[0].key]["outcome_a"]=1
    with pytest.raises(ValueError):
        fit_fold(parts,bad,"logistic")


def test_diagnostics_degenerate_and_finite():
    assert calibration_diagnostics([0,1],[.5,.5])["status"]=="UNDEFINED_DEGENERATE"
    d=calibration_diagnostics([0,1,0,1,0,1],[.2,.2,.4,.6,.8,.8])
    assert d["status"]=="DESCRIPTIVE_ONLY"
    assert np.isfinite(d["slope"]) and np.isfinite(d["intercept"])
