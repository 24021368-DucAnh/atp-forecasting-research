"""Synthetic TML event-level Elo timeline regression contracts (no third-party rows)."""
import csv
import hashlib
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
