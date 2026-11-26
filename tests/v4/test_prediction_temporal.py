"""S4.1: label-free fixture and strict point-in-time synthetic history."""
from dataclasses import fields, replace
from datetime import date

import pytest


CUTOFF = "2025-06-29T12:00:00Z"
EVENT = date(2025, 6, 30)
OBS = "2025-06-03T12:00:00Z"
READY = "2025-06-03T13:00:00Z"


def api():
    from atp_lab.prediction import temporal
    return temporal


def target(**changes):
    a = api()
    return replace(a.UpcomingFixture(
        "SYN-f", "SYN-target", "SYN-feed", 1, "SYN-event",
        EVENT, "HARD", "SYN-A", "SYN-B",
        "2025-06-28T12:00:00Z", "2025-06-28T13:00:00Z",
        "2025-06-30T14:00:00Z", "SCHEDULED"), **changes)


def history(**changes):
    a = api()
    return replace(a.HistoricalResult(
        "SYN-r1", "SYN-history", "SYN-feed", 1, "SYN-older-event",
        date(2025, 6, 1), "HARD", "SYN-A", "SYN-C",
        OBS, READY, "2025-06-02T16:00:00Z", "2025-06-02T14:00:00Z",
        "COMPLETED", "SYN-A"), **changes)


def choose(rows=(), fixture=None, cutoff=CUTOFF):
    return api().select_history(fixture or target(), tuple(rows), cutoff=cutoff)


def test_fixture_has_no_outcome_or_winner():
    names = {f.name for f in fields(target())}
    assert not names.intersection({"outcome", "outcome_a", "winner", "result", "label"})


def test_empty_history_is_valid():
    assert choose() == ()


def test_exact_28_day_cutoff_boundary():
    assert choose([history()]) == (history(
        observed_at="2025-06-03T12:00:00.000000Z",
        available_at="2025-06-03T13:00:00.000000Z",
        published_at="2025-06-02T16:00:00.000000Z",
        actual_start="2025-06-02T14:00:00.000000Z"),)
    assert choose([history(event_start=date(2025, 6, 2))]) == ()


def test_target_event_date_also_limits_maturity():
    fixture = target(event_start=date(2025, 6, 28))
    assert choose([history()], fixture=fixture) == ()


@pytest.mark.parametrize("change", [
    {"available_at":None},
    {"available_at":"2025-06-29T12:00:01Z"},
    {"observed_at":"2025-06-29T12:00:01Z",
     "available_at":"2025-06-29T13:00:00Z"},
    {"published_at":None},
    {"actual_start":None},
    {"state":"RETIRED"},
    {"state":"WALKOVER"},
    {"state":"VOID","winner":None},
    {"state":"UNKNOWN","winner":None},
])
def test_unavailable_or_ineligible_result_excluded(change):
    assert choose([history(**change)]) == ()


def test_availability_at_cutoff_is_eligible():
    selected = choose([history(available_at=CUTOFF)])
    assert len(selected) == 1


def test_same_event_and_same_match_never_enter_history():
    assert choose([history(tournament_id="SYN-event",event_start=EVENT,
                           actual_start="2025-06-30T14:00:00Z",
                           published_at="2025-06-30T16:00:00Z",
                           observed_at="2025-06-30T17:00:00Z",
                           available_at="2025-06-30T18:00:00Z")]) == ()
    assert choose([history(match_id="SYN-target",
                           player_b="SYN-B")]) == ()


def test_future_correction_does_not_change_earlier_history():
    first = history()
    correction = history(result_id="SYN-r2",revision=2,winner="SYN-C",
                         observed_at="2025-06-30T12:00:00Z",
                         available_at="2025-06-30T13:00:00Z")
    assert choose([correction,first]) == choose([first])


def test_visible_correction_replaces_older_revision():
    correction = history(result_id="SYN-r2",revision=2,winner="SYN-C",
                         observed_at="2025-06-05T12:00:00Z",
                         available_at="2025-06-05T13:00:00Z")
    selected = choose([history(),correction])
    assert len(selected) == 1 and selected[0].result_id == "SYN-r2"
    assert selected[0].winner == "SYN-C"


@pytest.mark.parametrize("available", [None,"2025-06-29T13:00:00Z"])
def test_latest_observed_unavailable_revision_blocks_stale_fallback(available):
    correction = history(result_id="SYN-r2",revision=2,winner="SYN-C",
                         observed_at="2025-06-29T11:00:00Z",
                         available_at=available)
    assert choose([history(),correction]) == ()


def test_void_correction_blocks_old_completed_result():
    correction = history(result_id="SYN-r2",revision=2,state="VOID",winner=None,
                         observed_at="2025-06-05T12:00:00Z",
                         available_at="2025-06-05T13:00:00Z")
    assert choose([history(),correction]) == ()


def test_multiple_visible_sources_for_match_rejected():
    a = api()
    with pytest.raises(a.TemporalError):
        choose([history(),history(result_id="SYN-r2",source_id="SYN-other")])


@pytest.mark.parametrize("change", [
    {"result_id":"SYN-r1","revision":2},
    {"result_id":"SYN-r2"},
    {"result_id":"SYN-r2","revision":2,"player_b":"SYN-D"},
    {"result_id":"SYN-r2","revision":2,"event_start":date(2025,5,31)},
    {"result_id":"SYN-r2","revision":2,"surface":"CLAY"},
])
def test_duplicate_or_conflicting_visible_identity_rejected(change):
    a = api()
    with pytest.raises(a.TemporalError):
        choose([history(),history(**change)])


@pytest.mark.parametrize("change", [
    {"state":"CANCELLED"}, {"state":"POSTPONED"}, {"state":"UNKNOWN"},
    {"available_at":None}, {"available_at":"2025-06-29T13:00:00Z"},
    {"observed_at":"2025-06-29T13:00:00Z",
     "available_at":"2025-06-29T13:00:00Z"},
    {"scheduled_start":None}, {"scheduled_start":CUTOFF},
    {"scheduled_start":"2025-06-29T11:00:00Z"},
    {"surface":"UNKNOWN"}, {"player_a":"SYN-B"},
    {"source_id":"REAL"}, {"revision":True},
    {"event_start":"2025-06-30"},
    {"scheduled_start":"2025-06-30T14:00:00"},
])
def test_blocked_target_fixture(change):
    a = api()
    with pytest.raises(a.TemporalError):
        choose(fixture=target(**change))


@pytest.mark.parametrize("change", [
    {"winner":"SYN-D"}, {"winner":None}, {"state":"LIVE"},
    {"state":"VOID","winner":"SYN-A"},
    {"available_at":"2025-06-03T11:00:00Z"},
    {"published_at":"2025-06-04T16:00:00Z"},
    {"actual_start":"2025-06-02T17:00:00Z"},
    {"event_start":date(2025,6,3)}, {"revision":0},
    {"surface":"UNKNOWN"}, {"player_a":"SYN-C"},
    {"observed_at":"2025-06-03T12:00:00-00:00"},
])
def test_malformed_history_rejected(change):
    a = api()
    with pytest.raises(a.TemporalError):
        choose([history(**change)])


def test_order_independent_and_canonical_utc():
    other = history(result_id="SYN-r3",match_id="SYN-history2",
                    event_start=date(2025,5,30),tournament_id="SYN-event2",
                    observed_at="2025-06-03T19:00:00+07:00")
    a = choose([history(),other])
    b = choose([other,history()])
    assert a == b
    assert [r.result_id for r in a] == ["SYN-r3","SYN-r1"]
    assert a[0].observed_at == "2025-06-03T12:00:00.000000Z"


def test_cutoff_naive_rejected():
    a = api()
    with pytest.raises(a.TemporalError):
        choose(cutoff="2025-06-29T12:00:00")
