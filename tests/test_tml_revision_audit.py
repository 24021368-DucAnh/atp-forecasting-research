"""Synthetic tests for the read-only provider revision research harness."""
import csv
import io

from atp_gate.tml_historical_audit import TML_COLUMNS
from scripts.tml_2025_revision_audit import compare_snapshots


def row(mid="", winner="A", loser="B", **extra):
    result=dict.fromkeys(TML_COLUMNS,"")
    result.update(tourney_id="2025-100",tourney_date="20250824",
                  tourney_level="G",surface="Hard",round="R32",
                  winner_id=winner,loser_id=loser,match_num=mid,score="6-4 6-4")
    result.update(extra)
    return result


def payload(rows):
    out=io.StringIO(newline="")
    writer=csv.DictWriter(out,fieldnames=TML_COLUMNS)
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode()


def test_missing_number_repaired_only_as_candidate():
    report=compare_snapshots(payload([row()]),payload([row("7")]))
    assert report["old_missing_match_num"]==1
    assert report["missing_disposition"]=={"REPAIRED_CANDIDATE":1}
    assert report["official_match_draw_verified"] is False
    assert report["eligible_for_model_training"]==0
    assert report["allocation_enabled"] is False


def test_swapped_winner_is_core_conflict():
    report=compare_snapshots(payload([row()]),payload([row("7","B","A")]))
    assert report["missing_disposition"]=={"CHANGED_CORE":1}


def test_ambiguous_old_candidate_across_numbered_and_unnumbered_rows():
    report=compare_snapshots(payload([row(),row("1")]),payload([row("7")]))
    assert report["missing_disposition"]=={"AMBIGUOUS_IDENTITY":1}


def test_duplicate_current_number_cannot_certify_repair():
    report=compare_snapshots(payload([row()]),payload([row("7"),row("7","C","D")]))
    assert report["missing_disposition"]=={"DUPLICATE_CURRENT_MATCH_KEY":1}


def test_unmatched_still_missing_and_existing_renumbering_separate():
    old=[row(),row("", "C","D"),row("5","E","F")]
    new=[row(),row("6","E","F"),row("9","G","H")]
    report=compare_snapshots(payload(old),payload(new))
    assert report["missing_disposition"]=={"MISSING_IN_CURRENT":1,"STILL_MISSING":1}
    assert report["numbered_disposition"]=={"NUMBER_CHANGED":1}
    assert report["new_unique_candidate_keys_absent_from_old"]==1


def test_missing_core_key_cannot_be_repaired():
    report=compare_snapshots(payload([row(winner="")]),payload([row("7",winner="")]))
    assert report["missing_disposition"]=={"INVALID_CANDIDATE_IDENTITY":1}


def test_core_conflicts_segmented_by_event_field_and_missing_status():
    old=[row(),row("", "C","D"),row("5","E","F")]
    new=[row("7",tourney_date="20250825"),
         row("8","C","D",score="7-5 6-4",tourney_date="20250825"),
         row("5","E","F",surface="Clay")]
    result=compare_snapshots(payload(old),payload(new))
    assert result["missing_core_changes_by_event"]=={
        "2025-100":{"changed_rows":2,"fields":{"score":1,"tourney_date":2}}}
    assert result["numbered_core_changes_by_event"]=={
        "2025-100":{"changed_rows":1,"fields":{"surface":1}}}
