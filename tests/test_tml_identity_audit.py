"""Synthetic P1.8 identity/coverage diagnostics; no third-party rows."""
import csv
import hashlib
import json

import pytest

from atp_gate.tml_historical_audit import TML_COLUMNS


def row(event="2024-example", num="1", winner="P01", loser="P02",
        round="F", start="20240219", **overrides):
    r = dict.fromkeys(TML_COLUMNS, "")
    r.update(tourney_id=event, tourney_name="Synthetic Event",
             tourney_level="250", surface="Hard", draw_size="32",
             tourney_date=start, match_num=num, winner_id=winner,
             loser_id=loser, winner_name="Synthetic " + winner,
             loser_name="Synthetic " + loser, round=round, score="6-4 6-3")
    r.update(overrides)
    return r


def snapshot(tmp_path, records, year=2024):
    path = tmp_path / f"{year}.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TML_COLUMNS)
        writer.writeheader()
        writer.writerows(records)
    return path


def audit(paths, pins=None):
    from atp_gate.tml_identity_audit import audit_tml_identity
    if pins is None:
        pins = {int(p.stem): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in paths}
    return audit_tml_identity(paths, expected_sha256=pins)


def test_valid_bracket_still_requires_external_review(tmp_path):
    path = snapshot(tmp_path, [
        row(num="1", winner="P01", loser="P02", round="SF"),
        row(num="2", winner="P03", loser="P04", round="SF"),
        row(num="3", winner="P01", loser="P03", round="F"),
    ])
    out = audit([path])
    assert out["counts"]["source_rows"] == 3
    assert out["counts"]["knockout_candidate_events"] == 1
    assert out["counts"]["candidate_disconnected_bracket_events"] == 0
    assert out["counts"]["candidate_loser_reappears_events"] == 0
    assert out["official_match_draw_verified"] is False
    assert out["individual_match_start_verified"] is False
    assert out["eligible_for_model_training"] == 0
    assert out["allocation_enabled"] is False and out["stake"] == 0
    assert "Synthetic" not in json.dumps(out)
    assert "P01" not in json.dumps(out)


def test_pins_must_cover_all_and_match_bytes(tmp_path):
    path = snapshot(tmp_path, [row()])
    with pytest.raises(ValueError, match="pin|SHA"):
        audit([path], {})
    with pytest.raises(ValueError, match="pin|SHA"):
        audit([path], {2024: "0"*64})
    with pytest.raises(ValueError, match="pin|SHA"):
        audit([path], {2024: hashlib.sha256(path.read_bytes()).hexdigest(),
                       2025: "0"*64})


def test_missing_and_numeric_duplicate_match_identity(tmp_path):
    path = snapshot(tmp_path, [
        row(num="1"), row(num="001"), row(num="", loser="P03"),
        row(num="bad", loser="P04"), row(num="2", winner="P01", loser="P01"),
    ])
    c = audit([path])["counts"]
    assert c["missing_match_num_rows"] == 1
    assert c["invalid_match_num_rows"] == 1
    assert c["noncanonical_match_num_rows"] == 1
    assert c["duplicate_numeric_match_key_groups"] == 1
    assert c["invalid_player_pair_rows"] == 1
    assert c["duplicate_candidate_pair_round_groups"] == 1


def test_swapped_winner_loser_same_round_is_duplicate_candidate(tmp_path):
    path = snapshot(tmp_path, [row(num="1"), row(num="2", winner="P02", loser="P01")])
    c = audit([path])["counts"]
    assert c["duplicate_candidate_pair_round_groups"] == 1
    assert c["conflicting_candidate_outcome_groups"] == 1


def test_player_name_conflicts_are_review_only_not_aliases(tmp_path):
    path = snapshot(tmp_path, [
        row(num="1"),
        row(num="2", winner_name="Changed Name", loser="P03", loser_name="Synthetic P02"),
    ])
    c = audit([path])["counts"]
    assert c["player_ids_with_multiple_name_tokens"] == 1
    assert c["name_tokens_with_multiple_player_ids"] == 1


def test_date_spread_and_previous_year_boundary(tmp_path):
    path = snapshot(tmp_path, [
        row(num="1", start="20231225"),
        row(num="2", start="20240104"),
        row(event="2024-one-day", num="3", start="20240219"),
        row(event="2024-one-day", num="4", start="20240220"),
        row(event="2024-invalid", start="20230219"),
    ])
    c = audit([path])["counts"]
    assert c["cross_year_start_rows"] == 1
    assert c["invalid_source_date_rows"] == 1
    assert c["date_spread_gt_one_day_events"] == 1
    assert c["one_day_date_variant_events"] == 1


def test_incomplete_and_impossible_knockout_graph(tmp_path):
    path = snapshot(tmp_path, [
        row(event="2024-incomplete", num="1", round="SF"),
        row(event="2024-impossible", num="1", round="SF"),
        row(event="2024-impossible", num="2", winner="P02", loser="P03", round="F"),
        row(event="2024-disconnected", num="1", round="SF"),
        row(event="2024-disconnected", num="2", winner="P03", loser="P04", round="F"),
        row(event="2024-special", num="1", round="RR", tourney_level="A"),
    ])
    c = audit([path])["counts"]
    assert c["knockout_candidate_events"] == 3
    assert c["candidate_missing_final_events"] == 1
    assert c["candidate_loser_reappears_events"] == 1
    assert c["candidate_disconnected_bracket_events"] == 1


def test_truncated_row_is_counted_not_fabricated(tmp_path):
    path = snapshot(tmp_path, [row()])
    with path.open("ab") as handle:
        handle.write(b"2024-truncated,partial\n")
    c = audit([path])["counts"]
    assert c["source_rows"] == 2
    assert c["malformed_rows"] == 1
    assert c["well_formed_rows"] == 1


def test_duplicate_candidates_are_segmented_by_main_tour_scope(tmp_path):
    path = snapshot(tmp_path, [
        row(event="2024-main", num="1"),
        row(event="2024-main", num="2"),
        row(event="2024-team", num="1", tourney_level="D"),
        row(event="2024-team", num="2", tourney_level="D"),
        row(event="2024-mixed", num="1"),
        row(event="2024-mixed", num="2", tourney_level="D"),
    ])
    out = audit([path])
    assert out["counts"]["duplicate_candidate_pair_round_groups"] == 3
    assert out["duplicate_candidate_groups_by_scope"] == {
        "MAIN_TOUR": 1, "OUTSIDE_MAIN_TOUR": 1, "MIXED_SCOPE": 1}


def test_season_inventory_does_not_invent_global_group_counts(tmp_path):
    path = snapshot(tmp_path, [
        row(num="1", start="20231225"),
        row(num="2", winner="P02", loser="P01"),
    ])
    out = audit([path])
    assert out["counts"]["conflicting_candidate_outcome_groups"] == 1
    local = out["source_inventory"][0]["counts"]
    assert "conflicting_candidate_outcome_groups" not in local
    assert local["cross_year_start_rows"] == 1
    assert local["invalid_source_date_rows"] == 0
