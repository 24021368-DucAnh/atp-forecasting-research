"""Fixed historical TML development experiment; never a production model.

Public runner verifies exact permission/protocol/source bytes before fitting.
Low-level fold functions are also used with synthetic unit-test data.
No serialization of estimators or per-match predictions.
"""
from __future__ import annotations

import hashlib
import json
import math
import warnings

from .tml_cohort_manifest import cohort_manifest
from .tml_development_data import split_fold, validate_matches
from .tml_development_features import FEATURE_NAMES, swap_features

PROTOCOL_SHA256="93776dc9949c6c49c16e8172630b606cd61fe328b25ce08a796a06b8ced3bca6"
PERMISSION_SHA256="2783d980d1ee2488c35a9206a2b270a71e78941c1a758a161aebf0a3c6b223d6"
MANIFEST_SHA256="b9b55b6c75f1f43394b3e69d19c6b791faedc8539908608ecf1d74dfaabcb8fb"
EPS=1e-12


def verify_research_permission(permission,protocol):
    if (type(permission) is not bytes or hashlib.sha256(permission).hexdigest()!=PERMISSION_SHA256
            or type(protocol) is not bytes or hashlib.sha256(protocol).hexdigest()!=PROTOCOL_SHA256):
        raise ValueError("explicit pinned research permission and protocol required")
    p=json.loads(permission)
    m=cohort_manifest()
    digest=hashlib.sha256(json.dumps(m,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    if (digest!=MANIFEST_SHA256 or p["manifest_sha256"]!=digest
            or p["protocol_sha256"]!=PROTOCOL_SHA256):
        raise ValueError("research cohort or protocol drift")
    return p


def symmetric_probability(a,b):
    import numpy as np
    a,b=np.asarray(a,dtype=float),np.asarray(b,dtype=float)
    if (a.shape!=b.shape or not np.isfinite(a).all() or not np.isfinite(b).all()
            or np.any((a<0)|(a>1)|(b<0)|(b>1))):
        raise ValueError("invalid paired probabilities")
    return np.clip((a+1-b)/2,EPS,1-EPS)


def _logit(p):
    import numpy as np
    p=np.clip(p,EPS,1-EPS)
    return np.log(p)-np.log1p(-p)


def _matrix(rows,features,names,*,swapped=False):
    import numpy as np
    out=[]
    for m in rows:
        if m.key not in features or set(features[m.key])!=set(FEATURE_NAMES):
            raise ValueError("missing or unexpected feature schema")
        f=features[m.key]
        if any(type(v) not in (int,float) or not math.isfinite(v) for v in f.values()):
            raise ValueError("nonfinite or invalid feature value")
        if swapped:
            f=swap_features(f)
        out.append([f[k] for k in names])
    return np.asarray(out,dtype=float)


def fit_fold(parts,features,model_name,*,feature_names=FEATURE_NAMES):
    """Low-level deterministic fold experiment; callers must gate real data.

    Evaluation outcomes never supplied to the fit or calibration methods.
    """
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.isotonic import IsotonicRegression
    from threadpoolctl import threadpool_limits
    names=tuple(feature_names)
    if (model_name not in ("logistic","xgboost") or not names or len(set(names))!=len(names)
            or not set(names)<=set(FEATURE_NAMES)):
        raise ValueError("unregistered model or feature schema")
    fit,cal,ev=(parts[k] for k in ("fit","calibration","evaluation"))
    if not all((fit,cal,ev)):
        raise ValueError("empty fit/calibration/evaluation partition")
    rows=validate_matches([*fit,*cal,*ev])
    years={m.start.year for m in ev}
    if len(years)!=1:
        raise ValueError("evaluation year mismatch")
    expected=split_fold(rows,next(iter(years)),require_support=False)
    for name,group in (("fit",fit),("calibration",cal),("evaluation",ev)):
        if {m.key for m in group}!={m.key for m in expected[name]}:
            raise ValueError("registered temporal partition mismatch")
    if any({m.outcome_a for m in group}!={0,1} for group in (fit,cal)):
        raise ValueError("both fit/calibration outcomes required")
    # Canonical ordering is independent of evaluation outcomes.
    fit,cal,ev=(expected[k] for k in ("fit","calibration","evaluation"))
    x=_matrix(fit,features,names)
    xs=_matrix(fit,features,names,swapped=True)
    y=np.array([m.outcome_a for m in fit],dtype=int)
    xx=np.vstack((x,xs)); yy=np.concatenate((y,1-y))
    scaler=None
    with threadpool_limits(limits=1):
        if model_name=="logistic":
            scaler=StandardScaler().fit(xx)
            model=LogisticRegression(C=1,solver="lbfgs",max_iter=2000)
            model.fit(scaler.transform(xx),yy)
        else:
            from xgboost import XGBClassifier
            model=XGBClassifier(n_estimators=160,max_depth=3,learning_rate=.04,
                subsample=.9,colsample_bytree=.9,min_child_weight=5,reg_lambda=2,
                objective="binary:logistic",eval_metric="logloss",random_state=29,
                n_jobs=1,tree_method="hist")
            model.fit(xx,yy)
        def predict(group):
            a=_matrix(group,features,names)
            b=_matrix(group,features,names,swapped=True)
            if scaler is not None:
                a,b=scaler.transform(a),scaler.transform(b)
            return symmetric_probability(model.predict_proba(a)[:,1],model.predict_proba(b)[:,1])
        pc=predict(cal)
        pe=predict(ev)
        cy=np.array([m.outcome_a for m in cal],dtype=int)
        mirrored=np.concatenate((pc,1-pc))
        labels=np.concatenate((cy,1-cy))
        platt=LogisticRegression(C=1,solver="lbfgs",max_iter=2000)
        platt.fit(_logit(mirrored).reshape(-1,1),labels)
        iso=IsotonicRegression(out_of_bounds="clip").fit(mirrored,labels)
        pp=symmetric_probability(platt.predict_proba(_logit(pe).reshape(-1,1))[:,1],
                                 platt.predict_proba(_logit(1-pe).reshape(-1,1))[:,1])
        pi=symmetric_probability(iso.predict(pe),iso.predict(1-pe))
    return {name:{m.key:float(p) for m,p in zip(ev,values)}
            for name,values in (("raw",pe),("platt",pp),("isotonic",pi))}


def calibration_diagnostics(labels,probabilities):
    """Evaluation-only unpenalized calibration regression; not fed back."""
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.exceptions import ConvergenceWarning
    from threadpoolctl import threadpool_limits
    y=np.asarray(labels)
    p=np.asarray(probabilities,dtype=float)
    if (y.ndim!=1 or p.shape!=y.shape or not np.isfinite(p).all()
            or np.any((p<0)|(p>1)) or not set(y.tolist())<={0,1}):
        raise ValueError("invalid diagnostic inputs")
    undef={"status":"UNDEFINED_DEGENERATE","slope":None,"intercept":None}
    if set(y.tolist())!={0,1} or np.ptp(p)<=1e-12:
        return undef
    x=_logit(p)
    if x[y==0].max()<=x[y==1].min() or x[y==1].max()<=x[y==0].min():
        return {"status":"UNDEFINED_SEPARATION","slope":None,"intercept":None}
    with warnings.catch_warnings(record=True) as seen, threadpool_limits(limits=1):
        warnings.simplefilter("always",ConvergenceWarning)
        # C=inf represents unpenalized logistic regression in current sklearn.
        reg=LogisticRegression(C=float("inf"),solver="lbfgs",max_iter=2000,tol=1e-9)
        reg.fit(x.reshape(-1,1),y)
    slope,intercept=float(reg.coef_[0,0]),float(reg.intercept_[0])
    if (any(issubclass(w.category,ConvergenceWarning) for w in seen)
            or not math.isfinite(slope) or not math.isfinite(intercept)):
        return {"status":"UNDEFINED_NONCONVERGENCE","slope":None,"intercept":None}
    return {"status":"DESCRIPTIVE_ONLY","slope":slope,"intercept":intercept}


def add_diagnostics(report,rows,predictions):
    for name,p in predictions.items():
        record=report["models"][name]
        record["calibration_slope_intercept"]=calibration_diagnostics(
            [m.outcome_a for m in rows],[p[m.key] for m in rows])
        for fold in record["folds"]:
            group=[m for m in rows if m.start.year==fold["year"]]
            fold["calibration_slope_intercept"]=calibration_diagnostics(
                [m.outcome_a for m in group],[p[m.key] for m in group])
    return report
