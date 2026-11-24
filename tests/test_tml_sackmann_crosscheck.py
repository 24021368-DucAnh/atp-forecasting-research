"""Two-source historical candidate cross-publication consistency audit.

All fixtures generated from made-up identifiers; no provider CSV redistributed.
"""
import csv
import json
from pathlib import Path

import pytest

from atp_gate.tml_historical_audit import TML_COLUMNS
from atp_gate.tml_sackmann_crosscheck import audit_tml_sackmann_crosspublication

ROOT=Path(__file__).resolve().parents[1]
REGISTRY=json.loads((ROOT/"docs/registries/tml_2024_feb_source_crosswalk_v1.json").read_text())
ALIASES=json.loads((ROOT/"docs/registries/tml_sackmann_2024_player_aliases_v1.json").read_text())
SACKMANN_COLUMNS=(
    "tourney_id,tourney_name,surface,draw_size,tourney_level,tourney_date,"
    "match_num,winner_id,winner_seed,winner_entry,winner_name,winner_hand,"
    "winner_ht,winner_ioc,winner_age,loser_id,loser_seed,loser_entry,"
    "loser_name,loser_hand,loser_ht,loser_ioc,loser_age,score,best_of,round,"
    "minutes,w_ace,w_df,w_svpt,w_1stIn,w_1stWon,w_2ndWon,w_SvGms,"
    "w_bpSaved,w_bpFaced,l_ace,l_df,l_svpt,l_1stIn,l_1stWon,l_2ndWon,"
    "l_SvGms,l_bpSaved,l_bpFaced,winner_rank,winner_rank_points,"
    "loser_rank,loser_rank_points"
).split(",")


def fixture_rows():
    tml,archive=[],[]
    seq=0
    for event in REGISTRY["entries"]:
        token=event["source_tourney_id"]
        numeric=token.split("-")[-1]
        archive_tid=token.split("-")[0]+"-"+numeric.zfill(4)
        for rnd,num in event["expected_rounds"].items():
            for _ in range(num):
                seq+=1
                wn=f"Winner{seq}"
                ln=f"Loser{seq}"
                if seq==1:
                    wn="Albert Ramos-Vinolas"
                if seq==28:
                    ln="Abdullah Shelbayh"
                sr="6-4 6-3"
                if event["official_event_key"]=="ATP_2024_BUENOS_AIRES" and rnd=="QF" and _==0:
                    sr="4-6 7-5 RET"
                t=dict.fromkeys(TML_COLUMNS,"")
                t.update(tourney_id=token,tourney_name=event["source_tourney_name"],
                         tourney_date=event["tourney_date"],surface=event["surface"],
                         match_num=str(seq),winner_id=f"TM{seq}",loser_id=f"TL{seq}",
                         winner_name=wn,loser_name=ln,round=rnd,score=sr,
                         draw_size="32",best_of="3",tourney_level="500")
                a=dict.fromkeys(SACKMANN_COLUMNS,"")
                a.update(tourney_id=archive_tid,tourney_name=event["source_tourney_name"],
                         tourney_date=event["tourney_date"],surface=event["surface"],
                         match_num=str(900-seq),winner_id=str(100000+seq),
                         loser_id=str(200000+seq),
                         winner_name=("Albert Ramos" if wn=="Albert Ramos-Vinolas" else wn),
                         loser_name=("Abedallah Shelbayh" if ln=="Abdullah Shelbayh" else ln),
                         round=rnd,score=("4-6 7-5 0-0 RET" if sr=="4-6 7-5 RET" else sr))
                tml.append(t)
                archive.append(a)
    return tml,archive


def write_csv(path,columns,rows):
    with path.open("w",newline="",encoding="utf-8") as h:
        writer=csv.DictWriter(h,fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def audit(tmp_path,mutate=None):
    tml,archive=fixture_rows()
    if mutate:
        mutate(tml,archive)
    a=tmp_path/"2024.csv"
    b=tmp_path/"atp_matches_2024.csv"
    write_csv(a,TML_COLUMNS,tml)
    write_csv(b,SACKMANN_COLUMNS,archive)
    return audit_tml_sackmann_crosspublication(a,b,REGISTRY,ALIASES)


def test_all_340_historical_candidates_crosscheck_with_explicit_aliases(tmp_path):
    r=audit(tmp_path)
    assert r["status"]=="CROSS_PUBLICATION_AGREEMENT_REVIEW_REQUIRED"
    assert r["target_tml_rows"]==340
    assert r["target_archive_rows"]==340
    assert r["matched_player_names_and_round"]==340
    assert r["exact_score_text_matches"]==339
    assert r["score_text_differences"]==1
    assert len(r["events"])==12
    assert len(r["tml_source_sha256"])==64
    assert len(r["archive_source_sha256"])==64
    assert r["official_match_draw_verified"] is False
    assert r["source_independence_verified"] is False
    assert r["eligible_for_model_training"]==0
    assert r["allocation_enabled"] is False and r["stake"]==0
    assert "Winner1" not in json.dumps(r)
    assert "Loser1" not in json.dumps(r)


def test_change_of_winner_name_flags_conflict_without_guessing(tmp_path):
    def mutate(tml,archive):
        archive[0]["winner_name"]="Another Person"
    r=audit(tmp_path,mutate)
    assert r["status"]=="CROSS_PUBLICATION_CONFLICT_REVIEW_REQUIRED"
    assert r["matched_player_names_and_round"]==339
    assert r["eligible_for_model_training"]==0


def test_duplicate_provider_match_row_rejected(tmp_path):
    def mutate(tml,archive):
        archive[1]["winner_name"]=archive[0]["winner_name"]
        archive[1]["loser_name"]=archive[0]["loser_name"]
        archive[1]["round"]=archive[0]["round"]
    with pytest.raises(ValueError,match="duplicate|ambiguous"):
        audit(tmp_path,mutate)


def test_dropped_event_rows_flag_incomplete(tmp_path):
    def mutate(tml,archive):
        del archive[-27:]
    r=audit(tmp_path,mutate)
    assert r["status"]=="CROSS_PUBLICATION_CONFLICT_REVIEW_REQUIRED"
    assert r["target_tml_rows"]==340
    assert r["target_archive_rows"]==313
    assert r["matched_player_names_and_round"]==313


def test_player_name_alias_registry_is_strict_and_nonfuzzy(tmp_path):
    x,y=fixture_rows()
    p=tmp_path/"2024.csv"
    q=tmp_path/"atp_matches_2024.csv"
    write_csv(p,TML_COLUMNS,x)
    write_csv(q,SACKMANN_COLUMNS,y)
    bad=dict(ALIASES)
    bad["version"]="auto_fuzzy"
    with pytest.raises(ValueError,match="alias|version"):
        audit_tml_sackmann_crosspublication(p,q,REGISTRY,bad)


def test_unexpected_archive_header_fails_closed(tmp_path):
    tml,archive=fixture_rows()
    p=tmp_path/"2024.csv"
    q=tmp_path/"atp_matches_2024.csv"
    write_csv(p,TML_COLUMNS,tml)
    write_csv(q,SACKMANN_COLUMNS[:-1],archive)
    with pytest.raises(ValueError,match="schema"):
        audit_tml_sackmann_crosspublication(p,q,REGISTRY,ALIASES)
