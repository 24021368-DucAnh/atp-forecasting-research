"""P1.9c regression contracts for local-only replay and honest provenance."""
import hashlib
import json
from pathlib import Path

import pytest

from scripts import p1_8c_cohort_research as replay
from test_tml_elo_experiment import season_files, _run_cli


def test_local_acquisition_no_network_and_all_bytes_pinned(tmp_path, monkeypatch):
    payloads = {y: str(y).encode() for y in range(2021, 2026)}
    pins = {y: hashlib.sha256(data).hexdigest() for y, data in payloads.items()}
    for y, data in payloads.items():
        (tmp_path / f"{y}.csv").write_bytes(data)
    def network_forbidden(*args, **kwargs):
        pytest.fail("offline mode attempted network acquisition")
    monkeypatch.setattr(replay, "verified_blob", network_forbidden)
    monkeypatch.setattr(replay, "update_tml_season", network_forbidden)
    actual, old, receipts = replay.acquire_sources(
        {"original_sha256": pins}, tmp_path, local_dir=tmp_path)
    assert actual == payloads and old is None
    assert set(receipts) == set(pins)
    for y, rec in receipts.items():
        assert rec["acquisition_mode"] == "LOCAL_PINNED_SNAPSHOT"
        assert rec["actual_fetch_uri"] is None
        assert rec["raw_sha256"] == pins[y]
        assert rec["local_filename"] == f"{y}.csv"


@pytest.mark.parametrize("problem", ["missing", "changed", "ambiguous"])
def test_local_preflight_rejects_bad_source(tmp_path, problem):
    data = b"synthetic"
    pin = hashlib.sha256(data).hexdigest()
    path = tmp_path / "2025.csv"
    if problem != "missing":
        path.write_bytes(data if problem != "changed" else data+b"x")
    if problem == "ambiguous":
        (tmp_path / f"2025-{pin}.csv").write_bytes(data)
    with pytest.raises(ValueError, match="source|SHA|ambiguous"):
        replay.acquire_sources({"original_sha256": {2025:pin}},
                               tmp_path, local_dir=tmp_path)


def test_network_provenance_separates_git_blob_and_publisher(tmp_path, monkeypatch):
    data = {2021:b"one",2025:b"two"}
    pins = {y:hashlib.sha256(b).hexdigest() for y,b in data.items()}
    old = b"old"
    monkeypatch.setattr(replay, "PINS", {2021:"blob-one",2025:"blob-old"})
    monkeypatch.setattr(replay, "SHA256", {2021:pins[2021],2025:hashlib.sha256(old).hexdigest()})
    monkeypatch.setattr(replay, "verified_blob", lambda pin: data[2021] if pin=="blob-one" else old)
    p = tmp_path / "2025.csv"
    p.write_bytes(data[2025])
    monkeypatch.setattr(replay, "update_tml_season", lambda *a, **kw: {"local_snapshot":str(p)})
    actual, archive, rec = replay.acquire_sources(
        {"original_sha256":pins,"revised_2025_url":"https://stats.tennismylife.org/data/2025.csv"},
        tmp_path)
    assert actual == data and archive[2025] == old
    assert rec[2021]["actual_fetch_uri"].endswith("/git/blobs/blob-one")
    assert rec[2025]["actual_fetch_uri"] == "https://stats.tennismylife.org/data/2025.csv"
    assert rec[2021]["acquisition_mode"] == "VERIFIED_GIT_BLOB"
    assert rec[2025]["acquisition_mode"] == "PINNED_PUBLISHER_DOWNLOAD"


def test_generic_loader_does_not_claim_download(tmp_path):
    from atp_gate.tml_elo_experiment import run_tml_elo_experiment
    report = run_tml_elo_experiment(season_files(tmp_path), bootstrap_replicates=50)
    for source in report["source_inventory"]:
        assert "source_url" not in source
        assert source["actual_fetch_uri"] is None
        assert source["acquisition_mode"] == "LOCAL_INPUT_UNATTESTED"
        assert source["nominal_publisher_url"].endswith(f"/{source['season']}.csv")


def test_cli_opt_in_normalization_reaches_pin_guard(tmp_path):
    paths = season_files(tmp_path)
    proc, report = _run_cli("tml-elo-experiment", *paths, "--normalize-level-a-2024",
                            "--out", tmp_path/"report.json")
    assert proc.returncode == 2
    assert report["status"] == "ERROR"
    assert "level-A normalization source SHA256" in report["reason"]
    assert report["stake"] == 0


def test_local_offline_cli_fails_without_input_instead_of_network(tmp_path, monkeypatch, capsys):
    def network_forbidden(*args, **kwargs):
        pytest.fail("offline fallback to network")
    monkeypatch.setattr(replay,"verified_blob",network_forbidden)
    monkeypatch.setattr(replay,"update_tml_season",network_forbidden)
    assert replay.main(["--local-dir",str(tmp_path)]) == 2
    result=json.loads(capsys.readouterr().out)
    assert result["status"]=="ERROR" and result["stake"]==0
