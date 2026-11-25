"""P2.2 synthetic contracts. No real rows or model fitting."""
from dataclasses import replace
from datetime import date
from math import log
import random

import pytest

from atp_gate.tml_development_data import DevelopmentMatch, validate_matches, split_fold, load_development_matches
from atp_gate.tml_development_features import build_features, swap_features, FEATURE_NAMES
from atp_gate.tml_skill_scoring import score_skill
from test_tml_elo_experiment import make_file, row, season_files


def m(event, num, day, a="A", b="Z", y=1, surface="Hard", tier="250", season=None):
    d=date.fromisoformat(day)
    return DevelopmentMatch(event,str(num),d,surface,tier,a,b,y,season or d.year)


def test_loader_preserves_exact_match_key_tier_and_calendar(tmp_path):
    records = load_development_matches(season_files(tmp_path))
    assert len(records)==17
    assert len({r.key for r in records})==17
    cross=next(r for r in records if r.event_id=="2025-cross")
    assert cross.key==("2025-cross","4") and cross.source_season==2025
    assert cross.start==date(2024,12,29) and cross.tier=="500"


@pytest.mark.parametrize("invalid", ["", "01", " 1", "1.0", "0"])
def test_bad_match_key_rejected(invalid):
    with pytest.raises(ValueError):
        validate_matches([replace(m("E",1,"2023-01-01"),match_num=invalid)])


def test_duplicate_and_inconsistent_event_metadata_rejected():
    a=m("E",1,"2023-01-01")
    for b in (a, replace(a,match_num="2",start=date(2023,1,2)),
              replace(a,match_num="2",tier="M")):
        with pytest.raises(ValueError):
            validate_matches([a,b])


def test_temporal_boundary_and_event_atomicity():
    rows=[m("warm",1,"2021-12-31"),m("fit",1,"2022-06-03"),
          m("gap1",1,"2022-06-04"),m("cal",1,"2022-07-01"),
          m("cal2",1,"2022-12-04"),m("gap2",1,"2022-12-05"),
          m("eval",1,"2023-01-01"),m("eval",2,"2023-01-01"),
          m("future",1,"2024-01-01")]
    parts=split_fold(rows,2023,require_support=False)
    assert [r.event_id for r in parts["fit"]]==["fit"]
    assert [r.event_id for r in parts["calibration"]]==["cal","cal2"]
    assert [r.event_id for r in parts["gap"]]==["gap1","gap2"]
    assert [r.event_id for r in parts["evaluation"]]==["eval","eval"]
    assert [r.event_id for r in parts["warmup"]]==["warm"]
    assert [r.event_id for r in parts["future"]]==["future"]
    with pytest.raises(ValueError,match="support"):
        split_fold(rows,2023)


def test_features_cutoff_same_event_and_future_label_invariance():
    rows=[m("prior",1,"2023-01-01"),m("early",1,"2023-01-28"),
          m("mature",1,"2023-01-29"),m("mature",2,"2023-01-29",y=0),
          m("future",1,"2023-02-26",y=0)]
    a=build_features(rows)
    b=build_features([replace(r,outcome_a=1-r.outcome_a) if r.event_id in ("mature","future") else r for r in rows])
    assert a[rows[1].key]==a[rows[0].key]
    assert a[rows[2].key]==a[rows[3].key]==b[rows[2].key]
    assert a[rows[2].key]["overall_elo_diff"]==24
    assert a[rows[2].key]["win_rate_90d_diff"]==pytest.approx(1/3)
    assert set(a[rows[2].key])==set(FEATURE_NAMES)
    shuffled=rows.copy();random.Random(1).shuffle(shuffled)
    assert build_features(shuffled)==a


def test_cold_start_orientation_and_window_expiry():
    rows=[m("prior",1,"2022-01-01"),m("late",1,"2023-01-03")]
    f=build_features(rows)
    a=f[rows[0].key]; b=f[rows[1].key]
    assert a["both_have_history"]==0 and a["overall_elo_diff"]==0
    assert b["both_have_history"]==1 and b["win_rate_365d_diff"]==0
    swapped=swap_features(b)
    assert swapped["overall_elo_diff"]==-b["overall_elo_diff"]
    assert swapped["log1p_h2h_count"]==b["log1p_h2h_count"]
    assert swap_features(swapped)==b


def test_skill_scorer_uses_all_keys_no_market_and_atp250():
    rows=[m("E",1,"2023-01-01"),m("F",1,"2024-01-01",y=0),m("G",1,"2025-01-01")]
    predictions={"global_elo":{r.key:.5 for r in rows},"candidate":{r.key:(.8 if r.outcome_a else .2) for r in rows}}
    out=score_skill(rows,predictions,replicates=50)
    assert out["n"]==3 and out["models"]["candidate"]["coverage"]==1
    assert out["models"]["candidate"]["log_loss"]==pytest.approx(-log(.8))
    assert out["models"]["candidate"]["brier"]==pytest.approx(.04)
    assert out["models"]["candidate"]["ece"]==pytest.approx(.2)
    assert out["tier_counts"]=={"250":3}
    assert out["model_validation_trusted"] is False
    assert out["allocation_enabled"] is False and out["stake"]==0


@pytest.mark.parametrize("problem",["missing","extra","nan","bool","out_of_range"])
def test_skill_scorer_fails_closed(problem):
    rows=[m("E",1,"2023-01-01"),m("F",1,"2024-01-01"),m("G",1,"2025-01-01")]
    base={r.key:.5 for r in rows}; bad=base.copy()
    if problem=="missing":bad.pop(rows[0].key)
    elif problem=="extra":bad[("fake","1")]=.5
    elif problem=="nan":bad[rows[0].key]=float("nan")
    elif problem=="bool":bad[rows[0].key]=True
    else:bad[rows[0].key]=1.1
    with pytest.raises(ValueError):
        score_skill(rows,{"global_elo":base,"candidate":bad},replicates=50)
