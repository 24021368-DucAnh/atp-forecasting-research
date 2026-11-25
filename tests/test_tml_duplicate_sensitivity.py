"""Research-only duplicate sensitivity; synthetic records."""
import csv
import hashlib
import io

import pytest

from atp_gate.tml_historical_audit import TML_COLUMNS


def row(num="1", event="2021-example", level="250", **kw):
    r = dict.fromkeys(TML_COLUMNS, "")
    r.update(tourney_id=event, match_num=num, tourney_level=level,
             winner_id="A", loser_id="B", round="R32", score="6-4 6-3",
             surface="Hard", tourney_date="20210301")
    r.update(kw)
    return r


def payload(rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=TML_COLUMNS)
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def derive(data, exact=0, conflict=0, mode="COLLAPSE_EXACT", pin=None):
    from atp_gate.tml_duplicate_sensitivity import derive_duplicate_snapshot
    return derive_duplicate_snapshot(
        data, season=2021, expected_sha256=pin or hashlib.sha256(data).hexdigest(),
        expected_exact_groups=exact, expected_conflicting_groups=conflict, mode=mode)


def records(data):
    return list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))


def test_exact_clone_retains_one_logical_record_not_an_official_id(tmp_path):
    data = payload([row("8"), row("2"), row("9", loser_id="C")])
    out, receipt = derive(data, exact=1)
    assert [r["match_num"] for r in records(out)] == ["2", "9"]
    assert receipt["removed_rows"] == 1
    assert receipt["exact_groups"] == 1
    assert receipt["official_match_id_verified"] is False
    assert receipt["source_sha256"] == hashlib.sha256(data).hexdigest()
    assert receipt["derived_sha256"] == hashlib.sha256(out).hexdigest()
    assert len(records(data)) == 3


def test_conflicting_statistics_never_choose_a_row():
    data = payload([row("1", minutes="80"), row("2", minutes="85")])
    out, receipt = derive(data, conflict=1)
    assert out == data
    assert receipt["removed_rows"] == 0
    out, receipt = derive(data, conflict=1, mode="COLLAPSE_EXACT_AND_QUARANTINE_CONFLICT")
    assert records(out) == []
    assert receipt["removed_rows"] == 2
    assert receipt["quarantined_rows"] == 2


def test_reversed_result_is_conflict_not_exact_clone():
    data = payload([row("1"), row("2", winner_id="B", loser_id="A")])
    out, receipt = derive(data, conflict=1, mode="COLLAPSE_EXACT_AND_QUARANTINE_CONFLICT")
    assert records(out) == []
    assert receipt["conflicting_groups"] == 1


def test_outside_main_tour_never_collapsed():
    data = payload([row("1", level="D"), row("2", level="D")])
    out, receipt = derive(data)
    assert out == data and receipt["removed_rows"] == 0


def test_mixed_scope_fails_closed():
    data = payload([row("1"), row("2", level="D")])
    with pytest.raises(ValueError, match="mixed"):
        derive(data)


def test_pin_and_expected_group_drift_fail_closed():
    data = payload([row("1"), row("2")])
    with pytest.raises(ValueError, match="SHA|pin"):
        derive(data, exact=1, pin="0"*64)
    with pytest.raises(ValueError, match="group"):
        derive(data, exact=0)


def test_missing_or_repeated_numeric_source_id_in_group_fails_closed():
    for nums in [("1", ""), ("1", "01"), ("1", "1")]:
        data = payload([row(nums[0]), row(nums[1])])
        with pytest.raises(ValueError, match="identity|number|key"):
            derive(data, exact=1)


def test_no_group_preserves_original_bytes_and_malformed_rows():
    data = payload([row()]) + b"truncated,partial\n"
    out, receipt = derive(data)
    assert out == data and receipt["malformed_rows"] == 1
    data = payload([row("1"), row("2")]) + b"truncated,partial\n"
    out, receipt = derive(data, exact=1)
    assert list(csv.reader(io.StringIO(out.decode())))[-1] == ["truncated", "partial"]
    assert receipt["malformed_rows"] == 1


def test_invalid_mode_and_header_rejected():
    data = payload([row()])
    with pytest.raises(ValueError, match="mode"):
        derive(data, mode="anything")
    with pytest.raises(ValueError, match="schema"):
        derive(b"wrong,header\n1,2\n")
