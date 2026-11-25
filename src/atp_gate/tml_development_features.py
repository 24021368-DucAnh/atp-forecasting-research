"""P2.2c: registered pre-event feature table, with frozen matured-date batches."""
from __future__ import annotations

from collections import Counter, defaultdict, deque
from datetime import timedelta
import math

from .tml_development_data import EMBARGO, validate_matches
from .tml_elo_experiment import _Ratings

FEATURE_NAMES=(
    "overall_elo_diff","surface_elo_diff","surface_shrinkage_elo_diff",
    "log1p_total_history_diff","log1p_surface_history_diff","win_rate_90d_diff",
    "win_rate_365d_diff","log1p_90d_count_diff","log1p_365d_count_diff",
    "smoothed_h2h_diff","log1p_h2h_count","min_history","min_surface_history",
    "both_have_history","both_have_surface_history","surface_hard","surface_clay","surface_grass",
)
SIGNED=frozenset(FEATURE_NAMES[:10])


def swap_features(features):
    if set(features)!=set(FEATURE_NAMES):
        raise ValueError("feature schema mismatch")
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in features.values()):
        raise ValueError("invalid feature value")
    return {k:-features[k] if k in SIGNED else features[k] for k in FEATURE_NAMES}


def build_features(matches):
    """Return local in-memory key -> allowlisted feature mapping; no label column."""
    rows=validate_matches(matches)
    by_date=defaultdict(list)
    for m in rows:
        by_date[m.start].append(m)
    days=sorted(by_date)
    ratings=_Ratings()
    total=Counter()
    meetings=Counter()
    wins=Counter()
    history=defaultdict(deque)
    cursor=0
    result={}
    for i,today in enumerate(days):
        while cursor<i and days[cursor]+EMBARGO<=today:
            batch=by_date[days[cursor]]
            ratings.update_matured_date(batch)
            for m in batch:
                a,b=m.player_a,m.player_b
                total.update((a,b))
                meetings[(a,b)]+=1
                wins[(a,b)]+=m.outcome_a
                history[a].append((m.start,m.outcome_a))
                history[b].append((m.start,1-m.outcome_a))
            cursor+=1
        def window(player,n):
            q=history[player]
            while q and q[0][0]<today-timedelta(days=365):
                q.popleft()
            subset=[y for d,y in q if d>=today-timedelta(days=n)]
            return (sum(subset)+1)/(len(subset)+2),len(subset)
        for m in by_date[today]:
            a,b=m.player_a,m.player_b
            ka,kb=(a,m.surface),(b,m.surface)
            ga,gb=ratings.overall.get(a,1500.),ratings.overall.get(b,1500.)
            sa,sb=ratings.surface.get(ka,1500.),ratings.surface.get(kb,1500.)
            na,nb=ratings.surface_n[ka],ratings.surface_n[kb]
            xa=ga+.35*na/(na+20)*(sa-1500)
            xb=gb+.35*nb/(nb+20)*(sb-1500)
            f90a,n90a=window(a,90); f90b,n90b=window(b,90)
            f365a,n365a=window(a,365); f365b,n365b=window(b,365)
            count=meetings[(a,b)]
            vals=(
                ga-gb,sa-sb,xa-xb,math.log1p(total[a])-math.log1p(total[b]),
                math.log1p(na)-math.log1p(nb),f90a-f90b,f365a-f365b,
                math.log1p(n90a)-math.log1p(n90b),math.log1p(n365a)-math.log1p(n365b),
                2*(wins[(a,b)]+1)/(count+2)-1,math.log1p(count),
                min(total[a],total[b]),min(na,nb),int(min(total[a],total[b])>0),
                int(min(na,nb)>0),int(m.surface=="Hard"),int(m.surface=="Clay"),int(m.surface=="Grass"),
            )
            result[m.key]=dict(zip(FEATURE_NAMES,vals))
    return result
