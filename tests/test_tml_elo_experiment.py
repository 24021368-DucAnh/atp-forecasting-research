"""Synthetic TML event-level Elo timeline regression contracts (no third-party rows)."""
import csv
import hashlib
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from atp_gate.tml_historical_audit import TML_COLUMNS
from atp_gate.tml_elo_experiment import orient_result, run_tml_elo_experiment


def row(season: int, event: str, start: str, match: int,
        winner: str = "A", loser: str = "Z", *,
        level: str = "500", surface: str = "Hard", score: str = "6-4 6-3"):
    r = dict.fromkeys(TML_COLUMNS, "")
    r.update(
        tourney_id=f"{season}-{event}", tourney_name=event,
        tourney_date=start, match_num=str(match),
        tourney_level=level, surface=surface, draw_size="32",
        winner_id=winner, loser_id=loser,
        winner_name="Synthetic W", loser_name="Synthetic L",
        score=score, best_of="3", round="R32",
    )
    return r


def make_file(root: Path, season: int, rows: list[dict], *,
              hash_name=False) -> Path:
    from io import StringIO
    stream = StringIO()
    writer = csv.DictWriter(stream, fieldnames=TML_COLUMNS)
    writer.writeheader()
    writer.writerows(rows)
    data = stream.getvalue().encode("utf-8")
    sha = hashlib.sha256(data).hexdigest()
    path = root / (f"{season}-{sha}.csv" if hash_name else f"{season}.csv")
    path.write_bytes(data)
    return path


def season_files(tmp_path):
    files = []
    for year in range(2021, 2026):
        a = [
            row(year, "warm", f"{year}0301", 1, winner="Q", loser="R"),
            row(year, "summer", f"{year}0701", 1, winner="R", loser="Q"),
        ]
        # Players A and Z have no pre-2023 history, so opening p=0.5.
        if year >= 2023:
            a += [row(year, "star", f"{year}0401", 2, winner="A", loser="Z"),
                  row(year, "star", f"{year}0401", 3, winner="A", loser="Z")]
        if year == 2025:
            # The file's nominal 2025 ATP season includes a 2024-start event.
            a += [row(year, "cross", "20241229", 4, winner="A", loser="Z")]
        files.append(make_file(tmp_path, year, a, hash_name=(year == 2024)))
    return files


def test_orientation_is_independent_of_csv_winner_first_order():
    assert orient_result("Z", "A") == ("A", "Z", 0)
    assert orient_result("A", "Z") == ("A", "Z", 1)
    with pytest.raises(ValueError):
        orient_result("A", "A")


def test_three_years_have_same_match_elo_and_coinflip_scores(tmp_path):
    report=run_tml_elo_experiment(season_files(tmp_path),bootstrap_replicates=50)
    assert report["status"]=="HISTORICAL_SKILL_RESEARCH_ONLY"
    assert report["mode"]=="PERSONAL_NONCOMMERCIAL_RESEARCH"
    assert report["fold_count"]==3
    assert [x["year"] for x in report["folds"]]==[2023,2024,2025]
    assert report["test_matches"]>=12
    assert report["aggregate"]["coinflip_brier"]==pytest.approx(0.25)
    assert report["aggregate"]["coinflip_log_loss"]==pytest.approx(0.69314718056)
    assert report["aggregate"]["n"]==sum(f["n"] for f in report["folds"])
    assert report["source_inventory"][0]["sha256"]
    assert report["model_validation_trusted"] is False
    assert report["t60_quote_verified"] is False
    assert report["allocation_enabled"] is False and report["stake"]==0
    assert report["participant_known_at_event_start"] is False


def test_same_tournament_two_wins_cannot_update_each_other(tmp_path):
    files=season_files(tmp_path)
    files[2]=make_file(tmp_path,2023,[
        row(2023,"star","20230401",1,winner="A",loser="Z"),
        row(2023,"star","20230401",2,winner="A",loser="Z"),
    ])
    out=run_tml_elo_experiment(files,bootstrap_replicates=50)
    first=out["folds"][0]
    # A/Z have no pre-2023 matches. Even the second result must see
    # the same 0.5 Elo probability, not learn from the first row.
    assert first["n"]==2
    assert first["global_elo_brier"]==pytest.approx(0.25)


def test_prior_tournament_within_28_days_cannot_leak(tmp_path):
    files=season_files(tmp_path)
    # Replace 2023 year with three events involving fresh X/Y players.
    rows=[
        row(2023,"new1","20230101",1,winner="X",loser="Y"),
        row(2023,"new2","20230120",1,winner="X",loser="Y"),
        row(2023,"new3","20230215",1,winner="X",loser="Y"),
    ]
    files[2]=make_file(tmp_path,2023,rows)
    result=run_tml_elo_experiment(files,bootstrap_replicates=50)
    fold=result["folds"][0]
    assert fold["n"]==3
    # First two forecasts p=0.5 despite positive outcomes in the first event.
    # At 2023-02-15 the Jan event has matured and contributes to prediction.
    assert 0.17 < fold["global_elo_brier"] < 0.25


def test_cross_year_season_event_is_scored_in_2024_not_2025(tmp_path):
    out=run_tml_elo_experiment(season_files(tmp_path),bootstrap_replicates=50)
    counts={f["year"]:f["n"] for f in out["folds"]}
    assert counts=={2023:4,2024:5,2025:4}


def test_exclude_retirements_and_ambiguous_levels(tmp_path):
    files=season_files(tmp_path)
    rows=[
        row(2023,"valid","20230301",1),
        row(2023,"retire","20230401",1,score="2-3 RET"),
        row(2023,"unknown","20230501",1,level="A"),
    ]
    files[2]=make_file(tmp_path,2023,rows)
    out=run_tml_elo_experiment(files,bootstrap_replicates=50)
    assert out["folds"][0]["n"]==1
    assert out["excluded_reasons"]["NON_COMPLETED"]>=1
    assert out["excluded_reasons"]["OUT_OF_SCOPE_LEVEL"]>=1


def test_invalid_hash_filename_cannot_be_accepted(tmp_path):
    files=season_files(tmp_path)
    bad=tmp_path/("2024-" + "0"*64 + ".csv")
    bad.write_bytes(files[3].read_bytes())
    with pytest.raises(ValueError, match="SHA|hash"):
        run_tml_elo_experiment([*files[:3],bad,*files[4:]])


def test_duplicate_tournament_match_key_is_rejected(tmp_path):
    files=season_files(tmp_path)
    data=[row(2023,"dupe","20230301",1),row(2023,"dupe","20230301",1)]
    files[2]=make_file(tmp_path,2023,data)
    with pytest.raises(ValueError, match="duplicate"):
        run_tml_elo_experiment(files)


def test_missing_holdout_years_fails_closed(tmp_path):
    files=season_files(tmp_path)
    with pytest.raises(ValueError, match="holdout|year"):
        run_tml_elo_experiment(files[:4])


def test_elo_event_bootstrap_is_seeded_and_descriptive(tmp_path):
    paths=season_files(tmp_path)
    a=run_tml_elo_experiment(paths,bootstrap_replicates=50,seed=11)
    b=run_tml_elo_experiment(paths,bootstrap_replicates=50,seed=11)
    assert a["bootstrap"]==b["bootstrap"]
    assert a["bootstrap"]["status"] in (
        "INSUFFICIENT_EVENT_SUPPORT","EVENT_BOOTSTRAP_DESCRIPTIVE_ONLY"
    )


def test_experiment_rejects_tournament_date_source_that_claims_future_season(tmp_path):
    files=season_files(tmp_path)
    files[1]=make_file(tmp_path,2022,[row(2022,"wrong","20240101",1)])
    with pytest.raises(ValueError, match="season|date"):
        run_tml_elo_experiment(files)


ROOT=Path(__file__).resolve().parents[1]


def _run_cli(*args):
    env={**os.environ,"PYTHONPATH":str(ROOT/"src")}
    proc=subprocess.run([sys.executable,"-m","atp_gate",*map(str,args)],
                        cwd=ROOT,env=env,text=True,capture_output=True,timeout=30)
    return proc,json.loads(proc.stdout)


def test_cli_persists_only_aggregate_experiment_report(tmp_path):
    files=season_files(tmp_path)
    report_path=tmp_path/"reports"/"elo.json"
    proc,report=_run_cli("tml-elo-experiment",*files,"--out",report_path)
    assert proc.returncode==0,proc.stderr+proc.stdout
    assert report["fold_count"]==3
    assert report["mode"]=="PERSONAL_NONCOMMERCIAL_RESEARCH"
    assert report["test_matches"]>=12
    assert json.loads(report_path.read_text(encoding="utf-8"))==report
    serialized=json.dumps(report)
    assert "Synthetic W" not in serialized
    assert "Synthetic L" not in serialized
    assert report["stake"]==0


def test_cli_refuses_to_replace_source_file_with_aggregate_report(tmp_path):
    files=season_files(tmp_path)
    untouched=files[0].read_bytes()
    proc,report=_run_cli("tml-elo-experiment",*files,"--out",files[0])
    assert proc.returncode==2
    assert report["status"]=="ERROR"
    assert report["allocation_enabled"] is False
    assert files[0].read_bytes()==untouched


def test_2025_public_rows_without_match_num_are_excluded_not_invented(tmp_path):
    files=season_files(tmp_path)
    # A second result with unknown match number cannot be de-duplicated safely.
    src=files[4]
    header=src.read_bytes().split(b"\n",1)[0]
    duplicate=src.read_bytes().split(b"\n",1)[1].splitlines()[0].replace(
        b"2025-warm,warm,Hard,32,500,,20250301,1,",
        b"2025-warm,warm,Hard,32,500,,20250301,,",
    )
    src.write_bytes(src.read_bytes()+duplicate+b"\n")
    report=run_tml_elo_experiment(files,bootstrap_replicates=50)
    assert report["excluded_reasons"]["MISSING_MATCH_ID"]==1
    assert report["folds"][2]["n"]==4
    assert report["stake"]==0


def test_truncated_2025_out_of_scope_row_is_quarantined(tmp_path):
    files=season_files(tmp_path)
    files[4].write_bytes(
        files[4].read_bytes()+b"2025-7696,Next Gen ATP Finals,Hard,8,A,I,20251222,15\n"
    )
    report=run_tml_elo_experiment(files,bootstrap_replicates=50)
    assert report["excluded_reasons"]["MALFORMED_ROWS"]==1
    assert report["mode"]=="PERSONAL_NONCOMMERCIAL_RESEARCH"


def test_one_day_variant_tourney_dates_are_grouped_before_elo_predictions(tmp_path):
    # Real TML 2024 Winston-Salem/Metz/Belgrade rows vary by one day.
    # A source's row date must never split one tournament into two updates.
    paths=season_files(tmp_path)
    paths[3]=make_file(tmp_path,2024,[
        row(2024,"variation","20240818",1,winner="A",loser="Z"),
        row(2024,"variation","20240819",2,winner="A",loser="Z"),
    ])
    result=run_tml_elo_experiment(paths,bootstrap_replicates=50)
    assert result["event_date_variants_grouped"]==1
    # The 2025 source also contains the Dec-2024 cross-year event.
    # Calendar-year fold 2024 must include that third match; the two
    # variable-date rows still belong to one event with frozen ratings.
    assert result["folds"][1]["n"]==3
    assert result["folds"][1]["global_elo_brier"] < 0.25


def test_multiweek_tournament_date_conflict_is_not_silently_normalized(tmp_path):
    paths=season_files(tmp_path)
    paths[3]=make_file(tmp_path,2024,[
        row(2024,"impossible","20240801",1),
        row(2024,"impossible","20240826",2),
    ])
    with pytest.raises(ValueError,match="start|date|spread"):
        run_tml_elo_experiment(paths,bootstrap_replicates=50)


def level_a_files(tmp_path):
    files = season_files(tmp_path)
    rows = [row(2024, "normal", "20240301", 1)]
    for event, name in (("451", "Doha"), ("7480", "Los Cabos")):
        for n in range(1, 28):
            record = row(2024, event, "20240219", n, level="A",
                         score="2-3 RET" if event == "451" and n == 27 else "6-4 6-3")
            record["tourney_name"] = name
            rows.append(record)
    rows.append(row(2024, "unreviewed", "20240501", 1, level="A"))
    files[3] = make_file(tmp_path, 2024, rows)
    return files


def pin_synthetic_level_a_source(monkeypatch, files):
    from atp_gate import tml_elo_experiment as experiment
    monkeypatch.setattr(experiment, "_LEVEL_A_2024_SHA256",
                        hashlib.sha256(files[3].read_bytes()).hexdigest(), raising=False)


def test_level_a_normalization_is_opt_in_and_preserves_filters(tmp_path, monkeypatch):
    files = level_a_files(tmp_path)
    pin_synthetic_level_a_source(monkeypatch, files)
    original = files[3].read_bytes()
    baseline = run_tml_elo_experiment(files, bootstrap_replicates=50)
    assert baseline["excluded_reasons"]["OUT_OF_SCOPE_LEVEL"] == 55
    normalized = run_tml_elo_experiment(files, bootstrap_replicates=50,
                                        normalize_level_a_2024=True)
    assert normalized["test_matches"] == baseline["test_matches"] + 53
    assert normalized["source_match_rows_eligible"] == baseline["source_match_rows_eligible"] + 53
    assert normalized["excluded_reasons"]["OUT_OF_SCOPE_LEVEL"] == 1
    assert normalized["excluded_reasons"]["NON_COMPLETED"] == 1
    audit = normalized["level_a_normalization"]
    assert audit["raw_rows"] == 54
    assert audit["eligible_rows"] == 53
    assert len(audit["registry_sha256"]) == 64
    assert audit["source_sha256"] == hashlib.sha256(original).hexdigest()
    assert normalized["allocation_enabled"] is False and normalized["stake"] == 0
    assert normalized["model_validation_trusted"] is False
    assert files[3].read_bytes() == original


def test_level_a_normalization_rejects_unpinned_source(tmp_path):
    files = level_a_files(tmp_path)
    with pytest.raises(ValueError, match="SHA|hash|pin"):
        run_tml_elo_experiment(files, normalize_level_a_2024=True,
                               bootstrap_replicates=50)


@pytest.mark.parametrize("field,value", [
    ("tourney_name", "Wrong tournament"),
    ("tourney_date", "20240220"),
    ("surface", "Clay"),
    ("tourney_level", "500"),
])
def test_level_a_normalization_rejects_metadata_drift(tmp_path, monkeypatch, field, value):
    files = level_a_files(tmp_path)
    with files[3].open(newline="", encoding="utf-8") as handle:
        records = list(csv.DictReader(handle))
    records[1][field] = value
    files[3] = make_file(tmp_path, 2024, records)
    pin_synthetic_level_a_source(monkeypatch, files)
    with pytest.raises(ValueError, match="metadata"):
        run_tml_elo_experiment(files, normalize_level_a_2024=True,
                               bootstrap_replicates=50)


def test_level_a_normalization_requires_complete_reviewed_event_counts(tmp_path, monkeypatch):
    files = level_a_files(tmp_path)
    with files[3].open(newline="", encoding="utf-8") as handle:
        records = list(csv.DictReader(handle))
    files[3] = make_file(tmp_path, 2024, records[0:1] + records[2:])
    pin_synthetic_level_a_source(monkeypatch, files)
    with pytest.raises(ValueError, match="count"):
        run_tml_elo_experiment(files, normalize_level_a_2024=True,
                               bootstrap_replicates=50)


def test_normalized_same_event_cannot_learn_its_own_results(tmp_path, monkeypatch):
    files = level_a_files(tmp_path)
    pin_synthetic_level_a_source(monkeypatch, files)
    result = run_tml_elo_experiment(files, normalize_level_a_2024=True,
                                    bootstrap_replicates=50)
    # All 53 newly accepted rows share one date. On the unmodified
    # replay their A/Z history is already known; the entire date batch
    # must nevertheless see exactly the same priors, irrespective of order.
    with files[3].open(newline="", encoding="utf-8") as handle:
        records = list(csv.DictReader(handle))
    files[3] = make_file(tmp_path, 2024, list(reversed(records)))
    pin_synthetic_level_a_source(monkeypatch, files)
    reordered = run_tml_elo_experiment(files, normalize_level_a_2024=True,
                                       bootstrap_replicates=50)
    assert result["aggregate"]["global_elo_log_loss"] == pytest.approx(
        reordered["aggregate"]["global_elo_log_loss"], abs=1e-12)
    assert result["aggregate"]["surface_elo_log_loss"] == pytest.approx(
        reordered["aggregate"]["surface_elo_log_loss"], abs=1e-12)


# P1.9b: reviewer regression cases; all inputs are synthetic.
@pytest.mark.parametrize("winner,loser", [(" P1 ", "P1"), ("P1", " P1 "), (" ", "P2"), ("P1", "\t")])
def test_invalid_canonical_identity_rejected(winner, loser):
    with pytest.raises(ValueError, match="identity"):
        orient_result(winner, loser)


def test_orientation_strips_outer_whitespace_without_casefolding():
    assert orient_result(" Z ", " A ") == ("A", "Z", 0)
    assert orient_result("a", "A") == ("A", "a", 0)


def test_invalid_identity_rows_are_counted_without_crash(tmp_path):
    paths = season_files(tmp_path)
    paths[2] = make_file(tmp_path, 2023, [
        row(2023, "valid", "20230301", 1),
        row(2023, "blank", "20230401", 1, winner="  ", loser="Z"),
        row(2023, "alias", "20230501", 1, winner=" A ", loser="A"),
    ])
    out = run_tml_elo_experiment(paths, bootstrap_replicates=50)
    assert out["excluded_reasons"]["INVALID_PLAYER_ID"] == 2
    assert out["folds"][0]["n"] == 1


@pytest.mark.parametrize("score", [
    "6-4 3-2 Default", "6-4 3-2 UNFINISHED", "6-4 3-2 ABANDONED",
    "6-4 3-2 IN PROGRESS", "0-0", "3-2", "6-4 0-0",
])
def test_incomplete_or_abnormal_score_not_eligible(tmp_path, score):
    paths = season_files(tmp_path)
    paths[2] = make_file(tmp_path, 2023, [
        row(2023, "valid", "20230301", 1),
        row(2023, "bad", "20230401", 1, score=score),
    ])
    out = run_tml_elo_experiment(paths, bootstrap_replicates=50)
    assert out["excluded_reasons"]["NON_COMPLETED"] == 1
    assert out["folds"][0]["n"] == 1


@pytest.mark.parametrize("score", ["6-4 6-3", "7-6(5) 6-7(4) 6-0", "6-7(3) 7-5 13-12(3)", "6-4 6-4 6-4"])
def test_completed_score_formats_remain_eligible(tmp_path, score):
    paths = season_files(tmp_path)
    paths[2] = make_file(tmp_path, 2023, [row(2023, "valid", "20230301", 1, score=score)])
    out = run_tml_elo_experiment(paths, bootstrap_replicates=50)
    assert out["folds"][0]["n"] == 1
