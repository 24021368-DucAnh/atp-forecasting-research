"""P2.2d: matched-key skill-only probability scoring, no market input."""
from __future__ import annotations

from collections import Counter,defaultdict
import math

from .tml_development_data import YEARS,validate_matches
from .tml_elo_experiment import _bootstrap

EPS=1e-12


def _metrics(rows,p):
    n=len(rows)
    pairs=[(m.outcome_a,p[m.key]) for m in rows]
    ll=math.fsum(-(y*math.log(max(EPS,min(1-EPS,x)))+
                   (1-y)*math.log1p(-max(EPS,min(1-EPS,x)))) for y,x in pairs)/n
    brier=math.fsum((x-y)**2 for y,x in pairs)/n
    bins=defaultdict(list)
    for y,x in pairs:
        bins[min(9,int(x*10))].append((y,x))
    base=math.fsum(y for y,_ in pairs)/n
    rel=res=ece=0.
    reliability=[]
    for i in range(10):
        group=bins[i]
        if not group:
            reliability.append({"bin":i,"n":0,"mean_probability":None,"observed_rate":None})
            continue
        k=len(group); avg=math.fsum(x for _,x in group)/k; rate=math.fsum(y for y,_ in group)/k
        w=k/n
        rel+=w*(avg-rate)**2;res+=w*(rate-base)**2;ece+=w*abs(avg-rate)
        reliability.append({"bin":i,"n":k,"mean_probability":avg,"observed_rate":rate})
    uncertainty=base*(1-base)
    return {"n":n,"coverage":1.0,"log_loss":ll,"brier":brier,"ece":ece,"reliability":reliability,
            "brier_decomposition":{"reliability":rel,"resolution":res,"uncertainty":uncertainty,
                                   "binning_residual":brier-(rel-res+uncertainty),
                                   "method":"BINNED_APPROXIMATION"},
            "calibration_slope_intercept":{"status":"DEFERRED_TO_P2_3_DIAGNOSTIC_FIT"}}


def score_skill(matches,predictions,*,replicates=2000,seed=29):
    rows=validate_matches(matches)
    if (type(replicates) is not int or not 50<=replicates<=5000 or type(seed) is not int
            or not isinstance(predictions,dict) or "global_elo" not in predictions
            or any(m.start.year not in YEARS for m in rows)):
        raise ValueError("invalid skill scorer scope/configuration")
    keys={m.key for m in rows}
    if {m.start.year for m in rows}!=set(YEARS):
        raise ValueError("all three development evaluation years required")
    for name,p in predictions.items():
        if not isinstance(name,str) or not name or not isinstance(p,dict) or set(p)!=keys:
            raise ValueError(f"matched key coverage mismatch: {name}")
        if any(type(x) not in (int,float) or not math.isfinite(x) or not 0<=x<=1 for x in p.values()):
            raise ValueError("invalid probability")
    by_year={y:[m for m in rows if m.start.year==y] for y in YEARS}
    models={}
    for name,p in predictions.items():
        out=_metrics(rows,p)
        out["folds"]=[{"year":y,**_metrics(group,p)} for y,group in by_year.items()]
        if name!="global_elo":
            baseline=predictions["global_elo"]
            paired={y:[(m.event_id,m.outcome_a,max(EPS,min(1-EPS,baseline[m.key])),
                        max(EPS,min(1-EPS,p[m.key]))) for m in group] for y,group in by_year.items()}
            boot=_bootstrap(list(YEARS),paired,replicates=replicates,seed=seed)
            out["minus_global_elo"]={
                "log_loss":out["log_loss"]-_metrics(rows,baseline)["log_loss"],
                "brier":out["brier"]-_metrics(rows,baseline)["brier"],
                "log_loss_95ci":boot["surface_elo_minus_global_elo_log_loss_95ci"],
                "brier_95ci":boot["surface_elo_minus_global_elo_brier_95ci"],
                "bootstrap":{k:v for k,v in boot.items() if not k.endswith("_95ci")},
                "brier_ci_probability_semantics":"CLIPPED_AT_1E_12_FOR_BOOTSTRAP_NUMERICS",
            }
        models[name]=out
    return {"schema":"TML_MATCHED_SKILL_SCORING_V1","status":"HISTORICAL_SKILL_RESEARCH_ONLY",
            "evaluation_status":"PREVIOUSLY_INSPECTED_DEVELOPMENT_YEARS",
            "n":len(rows),"tier_counts":dict(sorted(Counter(m.tier for m in rows).items())),
            "models":models,"official_match_draw_verified":False,"model_validation_trusted":False,
            "allocation_enabled":False,"stake":0}
