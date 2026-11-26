"""S4.2: synthetic parity with frozen V3 and immutable feature evidence."""
from dataclasses import replace
from datetime import date, timedelta
import math

import pytest

from atp_lab.prediction.temporal import UpcomingFixture, HistoricalResult, TemporalError
from atp_gate.tml_development_data import DevelopmentMatch
from atp_gate.tml_development_features import FEATURE_NAMES, build_features as legacy_features

DAY = date(2025, 7, 1)
CUTOFF = "2025-07-01T09:00:00Z"


def api():
    from atp_lab.prediction import features
    return features


def fixture(**changes):
    return replace(UpcomingFixture("SYN-f","SYN-target","SYN-feed",1,
        "SYN-target-event",DAY,"HARD","SYN-A","SYN-B",
        "2025-06-30T09:00:00Z","2025-06-30T10:00:00Z",
        "2025-07-01T12:00:00Z","SCHEDULED"),**changes)


def result(n=1, days=30, a="SYN-A", b="SYN-C", winner="SYN-A",
           surface="HARD", event=None):
    day = DAY-timedelta(days=days)
    clock = day.isoformat()
    return HistoricalResult(f"SYN-r{n}",f"SYN-m{n}","SYN-feed",1,
        event or f"SYN-event{n}",day,surface,a,b,
        clock+"T18:00:00Z",clock+"T19:00:00Z",clock+"T17:00:00Z",
        clock+"T15:00:00Z","COMPLETED",winner)


def snapshot(rows=(), target=None, cutoff=CUTOFF):
    return api().build_feature_snapshot(target or fixture(),tuple(rows),cutoff=cutoff)


def sample():
    return [result(1,365),result(2,90,b="SYN-B",winner="SYN-B"),
            result(3,90,a="SYN-B",winner="SYN-B",event="SYN-event2"),
            result(4,60,surface="CLAY",winner="SYN-C"),
            result(5,28,a="SYN-B",winner="SYN-C"),
            result(6,366,surface="GRASS"),
            result(7,27,b="SYN-B")]


def test_cold_start_exact_schema():
    a = api()
    snap = snapshot()
    assert a.FEATURE_NAMES == FEATURE_NAMES
    assert tuple(dict(snap.values)) == FEATURE_NAMES
    assert dict(snap.values) == dict(zip(FEATURE_NAMES,[0]*15+[1,0,0]))
    assert snap.result_ids == ()
    assert snap.fixture_id == "SYN-f"
    assert snap.cutoff == "2025-07-01T09:00:00.000000Z"
    assert len(snap.digest)==64 and all(c in "0123456789abcdef" for c in snap.digest)


@pytest.mark.parametrize("surface",["HARD","CLAY","GRASS"])
def test_synthetic_v3_parity_all_18_features(surface):
    rows = sample()
    target = fixture(surface=surface)
    # The legacy API requires a labeled target; this is a synthetic test
    # oracle only. V4 never receives a target outcome.
    legacy = [DevelopmentMatch(r.tournament_id,str(n+1),r.event_start,
               r.surface.title(),"250",r.player_a,r.player_b,
               int(r.winner==r.player_a),2025 if r.event_start.year==2025 else 2024)
              for n,r in enumerate(rows)]
    legacy.append(DevelopmentMatch(target.tournament_id,"1",DAY,
                  surface.title(),"250","SYN-A","SYN-B",0,2025))
    expected = legacy_features(legacy)[(target.tournament_id,"1")]
    actual = dict(snapshot(rows,target).values)
    assert tuple(actual)==FEATURE_NAMES
    assert actual == pytest.approx(expected,rel=1e-12,abs=1e-12)


def test_same_day_frozen_elo_not_sequential():
    rows = [result(1,30,b="SYN-B"),result(2,30,b="SYN-C",event="SYN-event1")]
    values = dict(snapshot(rows).values)
    assert values["overall_elo_diff"] == 36
    assert values["surface_elo_diff"] == 36
    assert values["min_history"] == 1


def test_windows_inclusive_90_and_365():
    rows = [result(1,90),result(2,91),result(3,365),result(4,366)]
    values = dict(snapshot(rows).values)
    assert values["log1p_90d_count_diff"] == pytest.approx(math.log1p(1))
    assert values["log1p_365d_count_diff"] == pytest.approx(math.log1p(3))
    assert values["log1p_total_history_diff"] == pytest.approx(math.log1p(4))


def test_order_and_equivalent_offset_do_not_change_snapshot():
    rows = sample()
    first = snapshot(rows)
    second = snapshot(list(reversed(rows)),cutoff="2025-07-01T16:00:00+07:00")
    assert first == second


def test_future_and_unavailable_revision_do_not_leak():
    old = result()
    first = snapshot([old])
    future = replace(old,result_id="SYN-r2",revision=2,winner="SYN-C",
                     observed_at="2025-07-01T10:00:00Z",
                     available_at="2025-07-01T11:00:00Z")
    assert snapshot([future,old]) == first
    blocked = replace(future,observed_at="2025-07-01T08:00:00Z",available_at=None)
    assert snapshot([old,blocked]) == snapshot()


def test_digest_binds_cutoff_fixture_and_selected_lineage():
    row = result()
    first = snapshot([row])
    assert snapshot([row],cutoff="2025-07-01T09:01:00Z").digest != first.digest
    assert snapshot([row],target=fixture(fixture_id="SYN-new")).digest != first.digest
    revised = replace(row,result_id="SYN-new-result",revision=2)
    second = snapshot([revised])
    assert second.values == first.values
    assert second.digest != first.digest
    assert second.result_ids == ("SYN-new-result",)


def test_event_metadata_conflict_rejected():
    rows = [result(1,30,event="SYN-one"),result(2,31,event="SYN-one")]
    with pytest.raises(TemporalError):
        snapshot(rows)


def test_same_event_not_used_even_if_mature():
    row = result(1,30,event="SYN-target-event")
    assert snapshot([row]) == snapshot()


def test_earlier_cutoff_stricter_than_target_date():
    row = result(1,28)
    early = fixture(observed_at="2025-06-29T09:00:00Z",
                    available_at="2025-06-29T10:00:00Z")
    assert snapshot([row],target=early,cutoff="2025-06-30T09:00:00Z").result_ids == ()
