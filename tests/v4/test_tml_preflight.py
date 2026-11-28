import csv
from hashlib import sha256
import io

import pytest
from atp_gate.tml_historical_audit import TML_COLUMNS

T1 = "2026-11-28T10:00:00Z"
T2 = "2026-11-28T11:00:00Z"
EVENT = "2026-SYN"


def row(number="1", **changes):
    values = dict(tourney_id=EVENT, tourney_date="20261116", match_num=number,
                  winner_id="SYN-A", loser_id="SYN-B", tourney_level="A",
                  surface="Hard", round="R32", score="6-4 6-4", best_of="3")
    values.update(changes)
    return {name: values.get(name, "") for name in TML_COLUMNS}


def payload(*rows):
    handle = io.StringIO(newline="")
    writer = csv.DictWriter(handle, fieldnames=TML_COLUMNS)
    writer.writeheader()
    writer.writerows(rows)
    return handle.getvalue().encode("utf-8")


def inspect(raw, **changes):
    from atp_lab.intake.tml_preflight import inspect_snapshot
    options = dict(expected_sha256=sha256(raw).hexdigest(), year=2026,
                   event_id=EVENT, inspected_at=T1)
    options.update(changes)
    return inspect_snapshot(raw, **options)


def test_selected_event_is_historical_candidate_only():
    raw = payload(row(), row("2", tourney_id="2026-OTHER"))
    report = inspect(raw)
    assert report.source_rows == 2 and report.selected_rows == 1
    assert report.sha256 == sha256(raw).hexdigest()
    assert report.status == "HISTORICAL_REVIEW_REQUIRED"
    match, = report.candidates
    assert (match.match_num, match.tournament_week, match.winner_id) == ("1", "2026-11-16", "SYN-A")
    assert match.provider_level == "A" and match.canonical_tier is None
    assert match.actual_start is None and match.published_at is None and match.available_at is None
    assert report.inspected_at == T1 and report.observed_at is None
    assert not report.eligible_for_training and not report.eligible_for_scoring


@pytest.mark.parametrize("options", [{"expected_sha256":"0"*64}, {"year":True},
    {"year":2027}, {"event_id":"../other"}, {"inspected_at":"2026-11-28"}])
def test_invalid_scope_or_receipt_fails_closed(options):
    with pytest.raises(ValueError):
        inspect(payload(row()), **options)


@pytest.mark.parametrize("raw", [b"<html>not csv</html>", b"\xff", b"", payload(row(),row())])
def test_reuses_legacy_schema_and_duplicate_rejection(raw):
    with pytest.raises(ValueError):
        inspect(raw)


@pytest.mark.parametrize("change, reason", [({"round":"Q1"},"UNSUPPORTED_SCOPE"),
    ({"tourney_level":"D"},"UNSUPPORTED_SCOPE"), ({"surface":"Unknown"},"UNKNOWN_SURFACE"),
    ({"score":"6-1 RET"},"OUTCOME_REVIEW_REQUIRED"), ({"score":"W/O"},"OUTCOME_REVIEW_REQUIRED"),
    ({"score":""},"OUTCOME_REVIEW_REQUIRED"), ({"winner_id":" "},"INVALID_PLAYER_IDS"),
    ({"match_num":""},"MISSING_MATCH_ID"), ({"tourney_date":"20261203"},"FUTURE_EVENT_DATE")])
def test_quarantine_retains_counts_without_fabricating_rows(change,reason):
    report = inspect(payload(row(), row("2", **change)))
    assert len(report.candidates) == 1 and report.selected_rows == 2
    assert dict(report.quarantine) == {reason: 1}
    assert not report.eligible_for_scoring


def test_incremental_diff_separates_new_correction_missing_and_unchanged():
    from atp_lab.intake.tml_preflight import compare_snapshots
    prior = inspect(payload(row("1"),row("2"),row("3")))
    current = inspect(payload(row("1"),row("2",score="7-5 6-4"),row("4")),inspected_at=T2)
    assert [(d.match_num,d.status) for d in compare_snapshots(prior,current)] == [
        ("1","UNCHANGED"),("2","CHANGED"),("3","NOT_OBSERVED"),("4","NEW")]
    assert prior.candidates[1].score == "6-4 6-4"


def test_changed_player_pair_and_quarantined_row_are_not_updates():
    from atp_lab.intake.tml_preflight import compare_snapshots
    prior=inspect(payload(row("1"),row("2")))
    current=inspect(payload(row("1",winner_id="SYN-C"),row("2",score="W/O")),inspected_at=T2)
    assert [(d.match_num,d.status) for d in compare_snapshots(prior,current)] == [
        ("1","IDENTITY_CONFLICT"),("2","QUARANTINED")]


def test_absent_event_does_not_delete_prior_rows():
    from atp_lab.intake.tml_preflight import compare_snapshots
    prior=inspect(payload(row()))
    current=inspect(payload(row(tourney_id="2026-OTHER")),inspected_at=T2)
    assert current.status == "EVENT_NOT_OBSERVED"
    assert [(d.match_num,d.status) for d in compare_snapshots(prior,current)] == [("1","NOT_OBSERVED")]


def test_same_hash_later_inspection_is_unchanged_and_backward_time_rejected():
    from atp_lab.intake.tml_preflight import compare_snapshots
    raw=payload(row()); prior=inspect(raw); current=inspect(raw,inspected_at=T2)
    assert compare_snapshots(prior,current)[0].status == "UNCHANGED"
    with pytest.raises(ValueError): compare_snapshots(current,prior)
    with pytest.raises(ValueError): compare_snapshots(prior,inspect(raw,event_id="2026-OTHER",inspected_at=T2))


def test_one_event_cannot_mix_candidate_tournament_weeks():
    with pytest.raises(ValueError):
        inspect(payload(row("1"), row("2", tourney_date="20261123")))


def test_historical_flags_and_missing_clocks_are_not_constructor_overrides():
    from dataclasses import replace
    report = inspect(payload(row()))
    with pytest.raises((TypeError, ValueError)):
        replace(report, eligible_for_training=True)
    with pytest.raises((TypeError, ValueError)):
        replace(report.candidates[0], actual_start=T1)


def test_row_returning_from_quarantine_is_not_counted_as_new():
    from atp_lab.intake.tml_preflight import compare_snapshots
    prior=inspect(payload(row("1", score="W/O")))
    current=inspect(payload(row("1")), inspected_at=T2)
    assert compare_snapshots(prior,current)[0].status == "REVIEW_RESOLVED"
