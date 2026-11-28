"""Fictional pre-import contracts; no provider network or database writes."""
from dataclasses import replace
from hashlib import sha256
import csv
import io

import pytest

from atp_gate.tml_historical_audit import TML_COLUMNS
from atp_lab.intake.tml_preflight import inspect_snapshot


def inputs():
    from atp_lab.intake.draw_audit import DrawScope, ReferenceDraw, ReferenceRow, MatchLink, PlayerLink
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=TML_COLUMNS)
    writer.writeheader()
    for num, rnd, score in (("1", "SF", "6-4 6-3"), ("2", "F", "7-6(4) 6-4")):
        data = dict(tourney_id="2024-SYN", tourney_date="20240212", match_num=num,
                    winner_id="T-A", loser_id="T-B" if num == "1" else "T-C",
                    tourney_level="A", surface="Hard", round=rnd, score=score, best_of="3")
        writer.writerow({k: data.get(k, "") for k in TML_COLUMNS})
    payload = stream.getvalue().encode()
    tml = inspect_snapshot(payload, expected_sha256=sha256(payload).hexdigest(), year=2024,
                           event_id="2024-SYN", inspected_at="2026-11-28T10:00:00Z")
    scope = DrawScope("2024-SYN", "ref-edition", "ref-feed", "2024-02-12", "2024-02-18",
                      "ATP_500", "HARD", (("SF", 1), ("F", 1)))
    reference = ReferenceDraw("ref-feed", "ref-edition", "b"*64, "ATP_500", "HARD", (
        ReferenceRow("R-1", "R-A", "R-B", "SF", "6-4 6-3", "COMPLETED", "2024-02-17", "c"*64),
        ReferenceRow("R-2", "R-A", "R-C", "F", "7-6(4) 6-4", "COMPLETED", "2024-02-18", "d"*64)))
    matches = (MatchLink("C-1", "1", "R-1"), MatchLink("C-2", "2", "R-2"))
    players = (PlayerLink("T-A", "R-A"), PlayerLink("T-B", "R-B"), PlayerLink("T-C", "R-C"))
    return tml, scope, reference, matches, players


def run(*args, **kw):
    from atp_lab.intake.draw_audit import audit_draw
    return audit_draw(*args, **kw)


def test_full_exact_agreement_is_review_only_and_does_not_claim_timing():
    report = run(*inputs(), lineage="DISTINCT_REVIEWED", lineage_evidence_sha256="e"*64)
    assert report.status == "AGREEMENT_REVIEW_REQUIRED"
    assert report.expected_rows == report.agreed_rows == 2
    assert report.full_result_agreement and report.reference_days_present == 2
    assert not report.source_independence_verified and not report.import_allowed
    assert not report.eligible_for_training and not report.eligible_for_scoring
    assert [(d.canonical_id, d.status) for d in report.decisions] == [("C-1", "AGREES"), ("C-2", "AGREES")]
    assert report.decisions[0].tml_row_sha256 == inputs()[0].candidates[0].row_sha256
    assert report.decisions[0].reference_row_sha256 == "c"*64
    assert report.actual_start_verified is False
    with pytest.raises((TypeError, ValueError)):
        replace(report, import_allowed=True)


@pytest.mark.parametrize("lineage, evidence, status", [
    ("UNKNOWN", None, "LINEAGE_REVIEW_REQUIRED"), ("SHARED", "e"*64, "SHARED_LINEAGE_REVIEW_REQUIRED")])
def test_agreement_does_not_override_unverified_or_shared_upstream(lineage, evidence, status):
    report = run(*inputs(), lineage=lineage, lineage_evidence_sha256=evidence)
    assert report.status == status and report.full_result_agreement and not report.import_allowed


@pytest.mark.parametrize("change, reason", [
    ({"winner_id": "R-B", "loser_id": "R-A"}, "OUTCOME_CONFLICT"),
    ({"score": "6-4 6-4"}, "SCORE_CONFLICT"), ({"round": "F"}, "ROUND_CONFLICT"),
    ({"loser_id": "R-C"}, "PLAYER_CONFLICT"), ({"status": "RETIRED"}, "NON_COMPLETED_REFERENCE"),
    ({"match_day": "2024-02-11"}, "MATCH_DAY_OUTSIDE_EVENT"),
])
def test_exact_mismatch_quarantines_even_when_other_match_agrees(change, reason):
    t, s, r, m, p = inputs()
    report = run(t, s, replace(r, rows=(replace(r.rows[0], **change), r.rows[1])), m, p)
    assert report.status == "CONFLICT_REVIEW_REQUIRED"
    assert report.agreed_rows == 1 and not report.full_result_agreement
    assert report.decisions[0].status == reason and not report.import_allowed


def test_missing_reference_and_missing_link_are_visible_not_deletions():
    t, s, r, m, p = inputs()
    missing = run(t, s, replace(r, rows=r.rows[:1]), m, p)
    assert missing.status == "CONFLICT_REVIEW_REQUIRED"
    assert missing.decisions[1].status == "REFERENCE_NOT_OBSERVED"
    unlinked = run(t, s, r, m[:1], p)
    assert unlinked.unlinked_tml == ("2",) and unlinked.unlinked_reference == ("R-2",)
    assert not unlinked.full_result_agreement


def test_expected_draw_not_inferred_from_matching_partial_feeds():
    t, s, r, m, p = inputs()
    report = run(t, replace(s, expected_rounds=(("SF", 2), ("F", 1))), r, m, p)
    assert report.agreed_rows == 2 and report.expected_rows == 3
    assert not report.full_result_agreement and "DRAW_COVERAGE_MISMATCH" in report.findings


def test_quarantined_or_unidentified_tml_rows_block_full_agreement():
    t, s, r, m, p = inputs()
    t = replace(t, selected_rows=3, quarantine=(("MISSING_MATCH_ID", 1),))
    report = run(t, s, r, m, p)
    assert not report.full_result_agreement and "TML_QUARANTINE" in report.findings


@pytest.mark.parametrize("which", ["duplicate-canonical", "duplicate-tml", "duplicate-reference", "duplicate-player", "same-bytes", "wrong-edition", "wrong-tier", "wrong-surface", "same-source", "missing-lineage-proof", "bad-digest"])
def test_ambiguous_links_and_invalid_reference_scope_fail_closed(which):
    t, s, r, m, p = inputs(); kw = {}
    if which == "duplicate-canonical": m = (m[0], replace(m[1], canonical_id="C-1"))
    if which == "duplicate-tml": m = (m[0], replace(m[1], tml_match_num="1"))
    if which == "duplicate-reference": m = (m[0], replace(m[1], reference_match_id="R-1"))
    if which == "duplicate-player": p = p + (replace(p[0], tml_player_id="T-D"),)
    if which == "same-bytes": r = replace(r, snapshot_sha256=t.sha256)
    if which == "wrong-edition": r = replace(r, event_id="other")
    if which == "wrong-tier": r = replace(r, tier="ATP_250")
    if which == "wrong-surface": r = replace(r, surface="CLAY")
    if which == "same-source": s=replace(s, reference_source_id="tml"); r=replace(r, source_id="tml")
    if which == "missing-lineage-proof": kw = {"lineage":"DISTINCT_REVIEWED"}
    if which == "bad-digest": r = replace(r, rows=(replace(r.rows[0], row_sha256="bad"), r.rows[1]))
    with pytest.raises(ValueError): run(t, s, r, m, p, **kw)


def test_no_name_matching_and_missing_exact_player_alias_is_quarantined():
    t, s, r, m, p = inputs()
    report = run(t, s, r, m, p[1:])
    assert all(d.status == "MISSING_PLAYER_ALIAS" for d in report.decisions)
    assert report.agreed_rows == 0


def test_unknown_match_day_is_not_invented_from_tournament_week():
    t, s, r, m, p = inputs()
    report = run(t, s, replace(r, rows=(replace(r.rows[0], match_day=None), r.rows[1])), m, p)
    assert report.reference_days_present == 1 and not report.actual_start_verified
    assert "REFERENCE_DAY_MISSING" in report.findings and not report.import_allowed


def test_deterministic_audit_digest_binds_inputs_not_order():
    t, s, r, m, p = inputs()
    a = run(t, s, r, m, p)
    b = run(t, s, replace(r, rows=r.rows[::-1]), m[::-1], p[::-1])
    assert a == b
    c = run(t, s, replace(r, snapshot_sha256="f"*64), m, p)
    assert c.audit_sha256 != a.audit_sha256


@pytest.mark.parametrize("score", ["0-0 0-0", "6-4 4-6", "6-4 6-4 4-6", "6-4(3) 6-4"])
def test_matching_invalid_score_is_not_corroboration(score):
    t, s, r, m, p = inputs()
    t = replace(t, candidates=(replace(t.candidates[0], score=score), t.candidates[1]))
    r = replace(r, rows=(replace(r.rows[0], score=score), r.rows[1]))
    report = run(t, s, r, m, p)
    assert report.decisions[0].status == "SCORE_REVIEW_REQUIRED"
    assert not report.full_result_agreement


def test_duplicate_player_in_same_elimination_round_is_conflict():
    t, s, r, m, p = inputs()
    t = replace(t, candidates=(t.candidates[0], replace(t.candidates[1], round="SF")))
    r = replace(r, rows=(r.rows[0], replace(r.rows[1], round="SF")))
    report = run(t, replace(s, expected_rounds=(("SF", 2),)), r, m, p)
    assert "ROUND_PLAYER_REUSE" in report.findings and not report.full_result_agreement
