"""TML February 2024 personal noncommercial source-audit RED contracts."""
import csv
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from atp_gate.tml_historical_audit import audit_tml_february_2024

ROOT=Path(__file__).resolve().parents[1]
REGISTRY=json.loads((ROOT/"docs/registries/tml_2024_feb_source_crosswalk_v1.json").read_text())
OFFICIAL=json.loads((ROOT/"docs/registries/atp_2024_february_official_events_v1.json").read_text())
COLUMNS=("tourney_id,tourney_name,surface,draw_size,tourney_level,indoor,"
         "tourney_date,match_num,winner_id,winner_seed,winner_entry,winner_name,"
         "winner_hand,winner_ht,winner_ioc,winner_age,winner_rank,winner_rank_points,"
         "loser_id,loser_seed,loser_entry,loser_name,loser_hand,loser_ht,loser_ioc,"
         "loser_age,loser_rank,loser_rank_points,score,best_of,round,minutes,"
         "w_ace,w_df,w_svpt,w_1stIn,w_1stWon,w_2ndWon,w_SvGms,w_bpSaved,"
         "w_bpFaced,l_ace,l_df,l_svpt,l_1stIn,l_1stWon,l_2ndWon,l_SvGms,"
         "l_bpSaved,l_bpFaced").split(",")


def synthetic_rows():
    rows=[]
    for event in REGISTRY["entries"]:
        match_num=1
        for rnd, count in event["expected_rounds"].items():
            for _ in range(count):
                row=dict.fromkeys(COLUMNS,"")
                row.update(
                    tourney_id=event["source_tourney_id"],
                    tourney_name=event["source_tourney_name"],
                    tourney_date=event["tourney_date"],
                    surface=event["surface"],
                    draw_size="32",
                    tourney_level=("A" if event["source_tourney_name"] in ("Doha","Los Cabos")
                                   else event["official_tier"].replace("ATP_","")),
                    match_num=str(match_num),round=rnd,best_of="3",
                    winner_id=f"W{match_num}_{event['source_tourney_id']}",
                    loser_id=f"L{match_num}_{event['source_tourney_id']}",
                    winner_name="Example Winner",loser_name="Example Loser",
                    score="6-4 6-3",
                )
                rows.append(row)
                match_num+=1
    return rows


def write_csv(path, rows, *, columns=COLUMNS):
    with path.open("w",newline="",encoding="utf-8") as handle:
        w=csv.DictWriter(handle,fieldnames=columns,extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def test_twelve_events_and_340_records_are_candidate_only(tmp_path):
    source=tmp_path/"2024.csv"
    write_csv(source,synthetic_rows())
    r=audit_tml_february_2024(source, REGISTRY, OFFICIAL)
    assert r["status"]=="SOURCE_CANDIDATE_REVIEW_REQUIRED"
    assert r["observed_target_matches"]==340
    assert r["observed_target_events"]==12
    assert len(r["events"])==12
    assert r["anomalies"]==[]
    assert r["mode"]=="PERSONAL_NONCOMMERCIAL_RESEARCH"
    assert len(r["source_sha256"])==64
    assert r["main_draw_verified"] is False
    assert r["eligible_for_model_training"]==0
    assert r["allocation_enabled"] is False and r["stake"]==0
    assert r["individual_match_start_verified"] is False


def test_duplicate_match_number_is_rejected(tmp_path):
    rows=synthetic_rows()
    rows[1]["match_num"]=rows[0]["match_num"]
    source=tmp_path/"2024.csv"
    write_csv(source,rows)
    r=audit_tml_february_2024(source, REGISTRY, OFFICIAL)
    assert r["status"]=="SOURCE_CANDIDATE_INCONSISTENT"
    assert any("DUPLICATE_MATCH" in x for x in r["anomalies"])


def test_wrong_player_identity_and_wrong_rounds_are_rejected(tmp_path):
    rows=synthetic_rows()
    rows[0]["winner_id"]=rows[0]["loser_id"]
    rows[1]["round"]="SF"
    source=tmp_path/"2024.csv"
    write_csv(source,rows)
    r=audit_tml_february_2024(source, REGISTRY, OFFICIAL)
    assert r["status"]=="SOURCE_CANDIDATE_INCONSISTENT"
    assert any("PLAYER_IDENTITY" in x for x in r["anomalies"])
    assert any("ROUND_HISTOGRAM" in x for x in r["anomalies"])


def test_official_event_registry_mismatch_fails(tmp_path):
    rows=synthetic_rows()
    source=tmp_path/"2024.csv"
    write_csv(source,rows)
    calendar=json.loads(json.dumps(OFFICIAL))
    calendar["events"][0]["official_tier"]="ATP_500"
    with pytest.raises(ValueError):
        audit_tml_february_2024(source,REGISTRY,calendar)


def test_missing_or_changed_schema_is_rejected(tmp_path):
    rows=synthetic_rows()
    source=tmp_path/"2024.csv"
    write_csv(source,rows,columns=COLUMNS[:-1])
    with pytest.raises(ValueError,match="schema"):
        audit_tml_february_2024(source,REGISTRY,OFFICIAL)


def test_missing_and_malformed_csv_refused(tmp_path):
    with pytest.raises(ValueError):
        audit_tml_february_2024(tmp_path/"notfound.csv",REGISTRY,OFFICIAL)
    source=tmp_path/"2024.csv"
    source.write_bytes(b"tourney_id,match_num\n\\xff\n")
    with pytest.raises(ValueError):
        audit_tml_february_2024(source,REGISTRY,OFFICIAL)


def test_missing_source_tournament_never_infers_rows(tmp_path):
    rows=synthetic_rows()
    source=tmp_path/"2024.csv"
    write_csv(source,[r for r in rows if r["tourney_id"]!="2024-407"])
    r=audit_tml_february_2024(source,REGISTRY,OFFICIAL)
    assert r["status"]=="SOURCE_CANDIDATE_INCONSISTENT"
    assert r["observed_target_events"]==11
    assert any("MISSING_EVENT" in a for a in r["anomalies"])
    assert r["eligible_for_model_training"]==0


def test_tml_a_level_cannot_upgrade_official_atp250(tmp_path):
    source=tmp_path/"2024.csv"
    write_csv(source,synthetic_rows())
    r=audit_tml_february_2024(source,REGISTRY,OFFICIAL)
    doha=next(x for x in r["events"] if x["official_event_key"]=="ATP_2024_DOHA")
    assert doha["official_tier"]=="ATP_250"
    assert doha["provider_levels"]==["A"]


def test_date_is_never_individual_match_date(tmp_path):
    source=tmp_path/"2024.csv"
    write_csv(source,synthetic_rows())
    r=audit_tml_february_2024(source,REGISTRY,OFFICIAL)
    assert r["source_date_semantics"]=="TOURNAMENT_START_DATE_NOT_MATCH_START"
    assert r["t60_quote_verified"] is False


def run_cli(*args):
    env={**os.environ,"PYTHONPATH":str(ROOT/"src")}
    process=subprocess.run(
        [sys.executable,"-m","atp_gate",*map(str,args)],
        env=env,cwd=ROOT,text=True,capture_output=True,timeout=30,
    )
    return process,json.loads(process.stdout)


def test_tml_cli_produces_safe_audit_report_without_copying_source(tmp_path):
    source=tmp_path/"2024.csv"
    write_csv(source,synthetic_rows())
    registry=tmp_path/"registry.json"
    registry.write_text(json.dumps(REGISTRY),encoding="utf-8")
    official=tmp_path/"official.json"
    official.write_text(json.dumps(OFFICIAL),encoding="utf-8")
    destination=tmp_path/"reports"/"tml.json"
    before=source.read_bytes()
    process,result=run_cli("tml-february-audit",source,registry,official,"--out",destination)
    assert process.returncode==0,process.stderr+process.stdout
    assert result["observed_target_matches"]==340
    assert result["mode"]=="PERSONAL_NONCOMMERCIAL_RESEARCH"
    assert result["eligible_for_model_training"]==0
    assert json.loads(destination.read_text())==result
    assert source.read_bytes()==before


def test_tml_cli_prevents_output_overwriting_raw_csv(tmp_path):
    source=tmp_path/"2024.csv"
    write_csv(source,synthetic_rows())
    registry=tmp_path/"registry.json"
    registry.write_text(json.dumps(REGISTRY),encoding="utf-8")
    official=tmp_path/"official.json"
    official.write_text(json.dumps(OFFICIAL),encoding="utf-8")
    original=source.read_bytes()
    process,result=run_cli("tml-february-audit",source,registry,official,"--out",source)
    assert process.returncode==2
    assert result["status"]=="ERROR"
    assert result["eligible_for_model_training"]==0
    assert source.read_bytes()==original
