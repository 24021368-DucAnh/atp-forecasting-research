"""Versioned TML direct CSV refresh, private noncommercial / no model promotion."""
import csv
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from io import StringIO

import pytest

from atp_gate.tml_snapshot import update_tml_season


NOW=datetime(2026,11,24,0,0,tzinfo=timezone.utc)
COLS=("tourney_id,tourney_name,surface,draw_size,tourney_level,indoor,"
      "tourney_date,match_num,winner_id,winner_seed,winner_entry,winner_name,"
      "winner_hand,winner_ht,winner_ioc,winner_age,winner_rank,winner_rank_points,"
      "loser_id,loser_seed,loser_entry,loser_name,loser_hand,loser_ht,loser_ioc,"
      "loser_age,loser_rank,loser_rank_points,score,best_of,round,minutes,"
      "w_ace,w_df,w_svpt,w_1stIn,w_1stWon,w_2ndWon,w_SvGms,w_bpSaved,"
      "w_bpFaced,l_ace,l_df,l_svpt,l_1stIn,l_1stWon,l_2ndWon,l_SvGms,"
      "l_bpSaved,l_bpFaced").split(",")


def sample_csv(*, year=2026, winner="ATPA", second=False):
    sio=StringIO()
    w=csv.DictWriter(sio,fieldnames=COLS)
    w.writeheader()
    first=dict.fromkeys(COLS,"")
    first.update(tourney_id=f"{year}-407",tourney_name="Example",
                 tourney_date=f"{year}1101",match_num="1",winner_id=winner,
                 loser_id="ATPB",winner_name="Winner",loser_name="Loser",
                 best_of="3",round="F",score="6-3 6-4",draw_size="32",
                 surface="Hard",tourney_level="500")
    w.writerow(first)
    if second:
        other=first.copy()
        other["match_num"]="2"
        other["winner_id"]="ATPC"
        other["loser_id"]="ATPD"
        w.writerow(other)
    return sio.getvalue().encode("utf-8")


def test_first_snapshot_creates_hash_named_file_and_safe_index(tmp_path):
    data=sample_csv()
    called=[]
    def fetch(url):
        called.append(url)
        return data
    report=update_tml_season(2026,tmp_path,at=NOW,fetcher=fetch)
    digest=hashlib.sha256(data).hexdigest()
    assert report["status"]=="NEW_SNAPSHOT_REVIEW_REQUIRED"
    assert report["sha256"]==digest
    assert report["source_rows"]==1
    assert called==["https://stats.tennismylife.org/data/2026.csv"]
    target=tmp_path/"2026"/f"2026-{digest}.csv"
    assert target.read_bytes()==data
    index=json.loads((tmp_path/"2026"/"index.json").read_text())
    assert index["latest_sha256"]==digest
    assert index["source_url"]==called[0]
    assert report["eligible_for_model_training"]==0
    assert report["allocation_enabled"] is False and report["stake"]==0


def test_throttled_refresh_does_not_make_network_request(tmp_path):
    data=sample_csv()
    update_tml_season(2026,tmp_path,at=NOW,fetcher=lambda _:data)
    def forbidden(_):
        raise AssertionError("daily throttle must avoid network request")
    report=update_tml_season(2026,tmp_path,at=NOW+timedelta(hours=2),fetcher=forbidden)
    assert report["status"]=="SKIPPED_INTERVAL"
    assert report["sha256"]==hashlib.sha256(data).hexdigest()


def test_same_data_unchanged_but_changed_data_preserves_old_version(tmp_path):
    a=sample_csv()
    b=sample_csv(second=True)
    first=update_tml_season(2026,tmp_path,at=NOW,fetcher=lambda _:a)
    unchanged=update_tml_season(
        2026,tmp_path,at=NOW+timedelta(hours=25),fetcher=lambda _:a,
    )
    assert unchanged["status"]=="UNCHANGED"
    changed=update_tml_season(
        2026,tmp_path,at=NOW+timedelta(hours=50),fetcher=lambda _:b,
    )
    assert changed["status"]=="NEW_SNAPSHOT_REVIEW_REQUIRED"
    assert changed["sha256"]!=first["sha256"]
    assert (tmp_path/"2026"/f"2026-{first['sha256']}.csv").read_bytes()==a
    assert (tmp_path/"2026"/f"2026-{changed['sha256']}.csv").read_bytes()==b


@pytest.mark.parametrize("bad",[
    b"<html><body>blocked</body></html>",
    b"",
    b"tourney_id,match_num\n2026-1,1\n",
    sample_csv(year=2025),
])
def test_bad_source_never_mutates_prior_snapshot(tmp_path,bad):
    original=sample_csv()
    first=update_tml_season(2026,tmp_path,at=NOW,fetcher=lambda _:original)
    index_path=tmp_path/"2026"/"index.json"
    stored=index_path.read_bytes()
    with pytest.raises(ValueError):
        update_tml_season(2026,tmp_path,at=NOW+timedelta(days=2),fetcher=lambda _:bad)
    assert index_path.read_bytes()==stored
    assert (tmp_path/"2026"/f"2026-{first['sha256']}.csv").read_bytes()==original


def test_existing_snapshot_tampering_is_rejected(tmp_path):
    data=sample_csv()
    first=update_tml_season(2026,tmp_path,at=NOW,fetcher=lambda _:data)
    snap=tmp_path/"2026"/f"2026-{first['sha256']}.csv"
    snap.write_bytes(b"manipulated")
    with pytest.raises(ValueError,match="hash|content|snapshot"):
        update_tml_season(2026,tmp_path,at=NOW+timedelta(days=2),fetcher=lambda _:data)


def test_duplicate_provider_match_ids_rejected(tmp_path):
    data=sample_csv()
    header,body=data.split(b"\n",1)
    duplicated=header+b"\n"+body+body
    with pytest.raises(ValueError,match="duplicate"):
        update_tml_season(2026,tmp_path,at=NOW,fetcher=lambda _:duplicated)


def test_bad_year_or_naive_clock_rejected_before_fetch(tmp_path):
    with pytest.raises(ValueError):
        update_tml_season(2027,tmp_path,at=NOW,fetcher=lambda _:sample_csv())
    with pytest.raises(ValueError):
        update_tml_season(2026,tmp_path,at=NOW.replace(tzinfo=None),fetcher=lambda _:sample_csv())


def test_manual_force_bypasses_refresh_interval_only(tmp_path):
    data=sample_csv()
    update_tml_season(2026,tmp_path,at=NOW,fetcher=lambda _:data)
    called=[]
    report=update_tml_season(
        2026,tmp_path,at=NOW+timedelta(hours=1),
        fetcher=lambda url:called.append(url) or data,force=True,
    )
    assert called
    assert report["status"]=="UNCHANGED"
    assert report["allocation_enabled"] is False


ROOT=Path(__file__).resolve().parents[1]


def run_cli(*args):
    env={**os.environ,"PYTHONPATH":str(ROOT/"src")}
    p=subprocess.run([sys.executable,"-m","atp_gate",*map(str,args)],
                     env=env,cwd=ROOT,text=True,capture_output=True,timeout=30)
    return p,json.loads(p.stdout)


def test_updater_cli_rejects_future_season_without_any_network(tmp_path):
    proc,report=run_cli("tml-update","--year","2027","--root",tmp_path)
    assert proc.returncode==2
    assert report["status"]=="ERROR"
    assert report["eligible_for_model_training"]==0
    assert report["allocation_enabled"] is False and report["stake"]==0
    assert not list(tmp_path.iterdir())


def test_historical_audit_accepts_sha_versioned_2024_filename(tmp_path):
    from atp_gate.tml_historical_audit import audit_tml_february_2024
    import json
    from pathlib import Path

    data=sample_csv(year=2024)
    sha=hashlib.sha256(data).hexdigest()
    path=tmp_path/f"2024-{sha}.csv"
    path.write_bytes(data)
    registry=json.loads((ROOT/"docs/registries/tml_2024_feb_source_crosswalk_v1.json").read_text())
    official=json.loads((ROOT/"docs/registries/atp_2024_february_official_events_v1.json").read_text())
    report=audit_tml_february_2024(path,registry,official)
    assert report["source_sha256"]==sha
    assert report["status"]=="SOURCE_CANDIDATE_INCONSISTENT"
    assert report["eligible_for_model_training"]==0


def test_season_2025_may_start_in_prior_december(tmp_path):
    # Real TML 2025 season begins with a tournament start 2024-12-29.
    rows=sample_csv(year=2025).replace(b"20251101", b"20241229")
    result=update_tml_season(
        2025,tmp_path,at=NOW,fetcher=lambda _:rows,
    )
    assert result["status"]=="NEW_SNAPSHOT_REVIEW_REQUIRED"
    assert result["source_rows"]==1
    assert result["eligible_for_model_training"]==0


def test_previous_season_early_december_cannot_sneak_into_update(tmp_path):
    data=sample_csv(year=2025).replace(b"20251101", b"20241201")
    with pytest.raises(ValueError,match="season"):
        update_tml_season(2025,tmp_path,at=NOW,fetcher=lambda _:data)


def test_public_source_missing_match_numbers_are_pinned_but_quarantined(tmp_path):
    # Real historical TML 2025 GitHub snapshot has many blank match_num rows.
    # Preserve exact original bytes without inventing match identity.
    first=sample_csv(year=2025)
    second=sample_csv(year=2025,winner="ATPC").split(b"\n",1)[1]
    # Same tournament but match_num blank is unidentifiable; never synthesize it.
    second=second.replace(b"2025-407,Example,Hard,32,500,,20251101,1,",
                          b"2025-407,Example,Hard,32,500,,20251101,,")
    source=first+second
    result=update_tml_season(2025,tmp_path,at=NOW,fetcher=lambda _:source)
    assert result["status"]=="SOURCE_ANOMALY_REVIEW_REQUIRED"
    assert result["source_rows"]==2
    assert result["accepted_rows"]==1
    assert result["source_anomalies"]["MISSING_MATCH_ID"]==1
    assert result["eligible_for_model_training"]==0
    assert (tmp_path/"2025"/f"2025-{result['sha256']}.csv").read_bytes()==source


def test_public_source_short_trailing_row_is_quarantined_not_repaired(tmp_path):
    good=sample_csv(year=2025)
    short=b"2025-7696,Next Gen ATP Finals,Hard,8,A,I,20251222,15\n"
    payload=good+short
    result=update_tml_season(2025,tmp_path,at=NOW,fetcher=lambda _:payload)
    assert result["status"]=="SOURCE_ANOMALY_REVIEW_REQUIRED"
    assert result["source_anomalies"]["MALFORMED_ROWS"]==1
    assert (tmp_path/"2025"/f"2025-{result['sha256']}.csv").read_bytes()==payload


def test_unidentifiable_only_source_is_still_rejected(tmp_path):
    all_missing=sample_csv(year=2025).replace(b"2025-407,Example,Hard,32,500,,20251101,1,",
                                               b"2025-407,Example,Hard,32,500,,20251101,,")
    with pytest.raises(ValueError,match="eligible|match"):
        update_tml_season(2025,tmp_path,at=NOW,fetcher=lambda _:all_missing)
    assert not (tmp_path/"2025"/"index.json").exists()
