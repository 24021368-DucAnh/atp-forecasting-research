"""Date-batched historical Elo/features for research only.

Surface-Elo defaults and equations follow the MIT licensed coenensam
`tennis-match-predictor` pinned at f548d978e09b3ef1a0783a1d315ec1fce1b6f70f.
The day-batch update is this project's safety modification: results of
matches on the same day are never used to build *that day's* features.

No per-match clock in the input => no certification of T−60 eligibility.
"""
from __future__ import annotations

from collections import defaultdict, deque
from datetime import date
from math import log10

import numpy as np
import pandas as pd

from .research_data import HistoricalMatch
from .feature_schema import FEATURE_NAMES


def _elo_prob(a: float, b: float) -> float:
    return 1.0 / (1.0 + 10.0 ** ((b - a) / 400.0))


def _k(n: int) -> float:
    return 250.0 / ((n + 5) ** 0.4)


class _History:
    def __init__(self):
        self.overall = defaultdict(lambda: 1500.0)
        self.surfaces = defaultdict(lambda: 1500.0)
        self.total = defaultdict(int)
        self.surface_count = defaultdict(int)
        self.form = defaultdict(lambda: deque(maxlen=10))
        self.sos = defaultdict(lambda: deque(maxlen=20))
        self.head = defaultdict(int)
        self.last_date: dict[str, date] = {}

    def rating(self, player: str, surface: str) -> float:
        key=(player,surface)
        n=self.surface_count[key]
        w=0.7*n/(n+20)
        return (1-w)*self.overall[player] + w*self.surfaces[key]

    def snapshot(self, m: HistoricalMatch) -> dict:
        a,b=m.player_a,m.player_b
        ra,rb=self.rating(a,m.surface),self.rating(b,m.surface)
        fa=sum(self.form[a])/len(self.form[a]) if self.form[a] else 0.5
        fb=sum(self.form[b])/len(self.form[b]) if self.form[b] else 0.5
        sosa=float(np.mean(self.sos[a])) if self.sos[a] else float('nan')
        sosb=float(np.mean(self.sos[b])) if self.sos[b] else float('nan')
        p_elo=_elo_prob(ra,rb)
        overround=(1/m.odds_a+1/m.odds_b) if m.odds_a and m.odds_b else None
        return {
            'date':m.day.isoformat(), 'source_row':m.source_row,
            'tournament':m.tournament, 'tier':m.tier, 'round_name':m.round_name,
            'surface':m.surface, 'player_a':a, 'player_b':b, 'y':m.y,
            'n_a':self.total[a], 'n_b':self.total[b],
            'odds_a':m.odds_a, 'odds_b':m.odds_b,
            'market_p_a': (1/m.odds_a)/overround if overround else float('nan'),
            'elo_diff':ra-rb, 'ov_diff':self.overall[a]-self.overall[b],
            'p_elo':p_elo, 'form_p1':fa, 'form_p2':fb,
            'h2h':self.head[(a,b)]-self.head[(b,a)],
            'rest_p1':min(60,(m.day-self.last_date[a]).days) if a in self.last_date else 30,
            'rest_p2':min(60,(m.day-self.last_date[b]).days) if b in self.last_date else 30,
            'rank_diff':float(m.rank_b-m.rank_a) if m.rank_a is not None and m.rank_b is not None else float('nan'),
            'min_nm':min(self.total[a],self.total[b]),
            'surface_clay':int(m.surface=='Clay'),
            'surface_grass':int(m.surface=='Grass'),
            'tour_wta':0,
            'spw_diff':float('nan'), 'rpw_diff':float('nan'),
            'ace_diff':float('nan'), 'bps_diff':float('nan'),
            'sos_diff':sosa-sosb,
        }

    def apply_result(self, m: HistoricalMatch):
        a,b=m.player_a,m.player_b
        winner, loser = (a,b) if m.y==1 else (b,a)
        ra,rb=self.rating(a,m.surface),self.rating(b,m.surface)
        pa=_elo_prob(ra,rb)
        actual=float(m.y)
        delta=actual-pa
        keya,keyb=(a,m.surface),(b,m.surface)
        na,nb=self.total[a],self.total[b]
        nsa,nsb=self.surface_count[keya],self.surface_count[keyb]
        self.overall[a]+=_k(na)*delta
        self.overall[b]-=_k(nb)*delta
        self.surfaces[keya]+=_k(nsa)*delta
        self.surfaces[keyb]-=_k(nsb)*delta
        self.total[a]+=1
        self.total[b]+=1
        self.surface_count[keya]+=1
        self.surface_count[keyb]+=1
        self.form[a].append(m.y)
        self.form[b].append(1-m.y)
        self.head[(winner,loser)]+=1
        if m.rank_a is not None:
            self.sos[b].append(m.rank_a)
        if m.rank_b is not None:
            self.sos[a].append(m.rank_b)
        self.last_date[a]=m.day
        self.last_date[b]=m.day


def replay_by_date(matches: list[HistoricalMatch]) -> pd.DataFrame:
    """Freeze each day's all pre-match feature vectors, then ingest its results."""
    history=_History()
    ordered=sorted(matches,key=lambda m:(m.day,m.tournament.casefold(),m.round_name.casefold(),
                                         m.player_a.casefold(),m.player_b.casefold()))
    records=[]
    pos=0
    while pos<len(ordered):
        until=pos+1
        while until<len(ordered) and ordered[until].day==ordered[pos].day:
            until+=1
        group=ordered[pos:until]
        records.extend(history.snapshot(m) for m in group)
        for match in group:
            history.apply_result(match)
        pos=until
    columns=['date','source_row','tournament','tier','round_name','surface',
             'player_a','player_b','y','n_a','n_b','odds_a','odds_b','market_p_a',*FEATURE_NAMES]
    return pd.DataFrame.from_records(records,columns=columns)
