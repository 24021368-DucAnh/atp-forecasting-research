"""P2.2a/b: retrospective TML match identity and registered event partitions.

Not a live fixture feed or a grant of model-training permission.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
import re
from typing import Sequence

from .tml_elo_experiment import _load
from .tml_cohort_manifest import cohort_manifest

YEARS = (2023, 2024, 2025)
EMBARGO = timedelta(days=28)
TIERS = frozenset({"250","500","M","G"})
SURFACES = frozenset({"Hard","Clay","Grass"})
PARTS = ("warmup","fit","calibration","gap","evaluation","future")
MATCH_NUM = re.compile(r"[1-9][0-9]{0,11}")


@dataclass(frozen=True)
class DevelopmentMatch:
    event_id: str
    match_num: str
    start: date
    surface: str
    tier: str
    player_a: str
    player_b: str
    outcome_a: int
    source_season: int

    @property
    def key(self) -> tuple[str,str]:
        return self.event_id, self.match_num


def _identifier(value):
    return isinstance(value,str) and bool(value) and value == value.strip() and not any(ord(c)<32 for c in value)


def validate_matches(matches: Sequence[DevelopmentMatch]) -> list[DevelopmentMatch]:
    if not isinstance(matches,(list,tuple)) or not matches:
        raise ValueError("empty or invalid match collection")
    seen=set()
    event_meta={}
    for m in matches:
        if (not isinstance(m,DevelopmentMatch) or not _identifier(m.event_id)
                or not isinstance(m.match_num,str) or MATCH_NUM.fullmatch(m.match_num) is None
                or type(m.start) is not date or type(m.source_season) is not int
                or not 2021 <= m.source_season <= 2025
                or not (m.start.year == m.source_season or
                        (m.start.year == m.source_season-1 and m.start.month==12 and m.start.day>=25))
                or m.tier not in TIERS or m.surface not in SURFACES
                or not _identifier(m.player_a) or not _identifier(m.player_b)
                or m.player_a >= m.player_b or type(m.outcome_a) is not int or m.outcome_a not in (0,1)):
            raise ValueError("invalid development match identity or metadata")
        if m.key in seen:
            raise ValueError("duplicate source match key")
        seen.add(m.key)
        meta=(m.start,m.surface,m.tier,m.source_season)
        if event_meta.setdefault(m.event_id,meta)!=meta:
            raise ValueError("inconsistent event metadata")
    return sorted(matches,key=lambda m:(m.start,m.event_id,int(m.match_num)))


def load_development_matches(paths: Sequence[Path], *, locked=False) -> list[DevelopmentMatch]:
    """Load via frozen parser; locked mode checks exact derived hashes and counts."""
    if type(locked) is not bool:
        raise ValueError("locked must be explicit boolean")
    matches, inventory, _, _, audit = _load(paths,normalize_level_a_2024=locked)
    result=validate_matches([DevelopmentMatch(m.event_id,m.match_num,m.start,m.surface,m.tier,
                                               m.player_a,m.player_b,m.outcome_a,m.source_season)
                             for m in matches])
    if locked:
        manifest=cohort_manifest()
        hashes={r["season"]:r["sha256"] for r in inventory}
        if (hashes!=manifest["derived_sha256"] or len(result)!=manifest["expected_eligible"]
                or audit is None or audit["registry_sha256"]!=manifest["level_a_registry_sha256"]
                or {y:sum(m.start.year==y for m in result) for y in YEARS}!=manifest["evaluation_by_year"]):
            raise ValueError("locked development cohort drift")
    return result


def split_fold(matches: Sequence[DevelopmentMatch], year: int, *, require_support=True) -> dict:
    if type(year) is not int or year not in YEARS or type(require_support) is not bool:
        raise ValueError("invalid registered evaluation year/support option")
    rows=validate_matches(matches)
    fit_start=date(2022,1,1)
    cal_start=date(year-1,7,1)
    eval_start=date(year,1,1)
    eval_end=date(year+1,1,1)
    parts={p:[] for p in PARTS}
    for m in rows:
        d=m.start
        if d<fit_start:
            name="warmup"
        elif d<cal_start:
            name="fit" if d+EMBARGO<=cal_start else "gap"
        elif d<eval_start:
            name="calibration" if d+EMBARGO<=eval_start else "gap"
        elif d<eval_end:
            name="evaluation"
        else:
            name="future"
        parts[name].append(m)
    if require_support:
        for name,min_rows,min_events in (("fit",500,12),("calibration",200,8),("evaluation",200,12)):
            selected=parts[name]
            if (len(selected)<min_rows or len({m.event_id for m in selected})<min_events
                    or (name!="evaluation" and {m.outcome_a for m in selected}!={0,1})):
                raise ValueError(f"insufficient registered {name} support")
    return parts
