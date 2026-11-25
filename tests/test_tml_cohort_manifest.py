"""Cohort lock and identity review contracts, synthetic inputs."""
import csv
import hashlib
import io
from pathlib import Path

import pytest

from atp_gate.tml_historical_audit import TML_COLUMNS


def payload(rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=TML_COLUMNS)
    writer.writeheader()
    for n, (w, wn, l, ln) in enumerate(rows, 1):
        row = dict.fromkeys(TML_COLUMNS, "")
        row.update(tourney_id="2021-test", match_num=str(n), tourney_level="250",
                   tourney_date="20210101", surface="Hard", round="R32",
                   winner_id=w, winner_name=wn, loser_id=l, loser_name=ln,
                   score="6-4 6-4")
        writer.writerow(row)
    return stream.getvalue().encode()


def test_identity_profile_normalizes_display_tokens_but_never_ids():
    from atp_gate.tml_cohort_manifest import profile_identity_variants
    data = payload([("A", "A Name", "B", "B Name"),
                    ("A", " A  NAME ", "C", "B Name"),
                    ("A", "Alternate Name", "B", "B Name")])
    p = profile_identity_variants([data])
    assert p["multiple_name_ids"] == 1
    assert p["multiple_id_names"] == 1
    assert p["variants"] == [{"player_id": "A",
                              "name_tokens": ["a name", "alternate name"]}]
    assert p["identity_remapped"] is False


def test_cohort_manifest_pins_both_original_and_derived_files():
    from atp_gate.tml_cohort_manifest import cohort_manifest
    m = cohort_manifest()
    assert m["expected_eligible"] == 12620
    assert m["expected_evaluated"] == 7694
    assert m["evaluation_by_year"] == {2023:2600, 2024:2647, 2025:2447}
    assert set(m["original_sha256"]) == set(range(2021, 2026))
    assert set(m["derived_sha256"]) == set(m["original_sha256"])
    assert m["original_sha256"][2021] != m["derived_sha256"][2021]
    assert m["original_sha256"][2024] == m["derived_sha256"][2024]
    assert m["official_match_draw_verified"] is False
    assert m["model_validation_trusted"] is False
    assert m["allocation_enabled"] is False and m["stake"] == 0
    assert m["evaluation_status"] == "PREVIOUSLY_INSPECTED_DEVELOPMENT_YEARS"


def test_preflight_rejects_missing_and_modified_bytes_before_processing():
    from atp_gate.tml_cohort_manifest import verify_pinned_inputs
    data = b"source"
    digest = hashlib.sha256(data).hexdigest()
    assert verify_pinned_inputs({2021:data}, {2021:digest}) is None
    for bad in ({}, {2021:b"modified"}, {2021:data, 2022:data}):
        with pytest.raises(ValueError, match="season|SHA"):
            verify_pinned_inputs(bad, {2021:digest})


def test_identity_profile_rejects_wrong_schema():
    from atp_gate.tml_cohort_manifest import profile_identity_variants
    with pytest.raises(ValueError, match="schema"):
        profile_identity_variants([b"wrong,header\n1,2\n"])


def test_manifest_is_fresh_and_not_caller_mutable():
    from atp_gate.tml_cohort_manifest import cohort_manifest
    m = cohort_manifest()
    m["original_sha256"][2021] = "0"*64
    m["expected_eligible"] = 0
    assert cohort_manifest()["original_sha256"][2021] != "0"*64
    assert cohort_manifest()["expected_eligible"] == 12620
