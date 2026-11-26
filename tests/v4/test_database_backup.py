"""S2.4: verified, non-destructive SQLite backup and restore."""
from contextlib import closing
from pathlib import Path
import sqlite3

import pytest

from atp_lab.database import identity as i, forecast as f
from atp_lab.database.connection import open_reader, open_writer
from atp_lab.database.migrations import migrate
from atp_lab.database.schema_v3 import verify_forecast_schema

OBS = "2026-01-01T08:00:00Z"
READY = "2026-01-01T09:00:00Z"
START = "2026-01-02T10:00:00Z"
DONE = "2026-01-02T12:00:00Z"


def api():
    from atp_lab.database import backup
    return backup


@pytest.fixture
def live(tmp_path):
    path = tmp_path / "source.sqlite"
    with closing(open_writer(path)) as c:
        migrate(c)
        i.migrate_identity(c)
        f.migrate_forecast(c)
        c.execute("PRAGMA wal_autocheckpoint=0")
        c.execute("BEGIN IMMEDIATE")
        i.put_source(c, i.Source("SYN-feed","SYNTHETIC","LOCKED"))
        i.put_snapshot(c, i.Snapshot("SYN-s1","SYN-feed","a"*64,OBS))
        i.put_snapshot(c, i.Snapshot("SYN-s2","SYN-feed","b"*64,DONE))
        i.put_player(c, i.Player("SYN-A"))
        i.put_player(c, i.Player("SYN-B"))
        i.put_tournament(c, i.Tournament("SYN-t","SYN-event","2026","ATP250","HARD"))
        i.put_match(c, i.Match("SYN-m","SYN-t","SYN-A","SYN-B"))
        i.append_fixture(c, i.Fixture("SYN-f","SYN-m",1,"SYN-feed","SYN-s1","SYN-A","SYN-B",OBS,READY,START,"SCHEDULED"))
        f.append_feature(c, f.FeatureSnapshot("SYN-feat","SYN-f","c"*64,READY))
        f.append_model(c, f.ModelVersion("SYN-model","d"*64,"e"*64,OBS,READY,"SYNTHETIC"))
        f.append_prediction(c, f.Prediction("SYN-p","SYN-m","SYN-f","SYN-feat","SYN-model",READY,.65,"f"*64))
        i.append_result(c, i.Result("SYN-r","SYN-m",1,"SYN-feed","SYN-s2",DONE,DONE,DONE,START,"COMPLETED","SYN-A"))
        f.append_evaluation(c, f.Evaluation("SYN-e","SYN-p","SYN-r",DONE,"RECORDED"))
        c.commit()
        yield c, path


def read_payload(path):
    with closing(open_reader(path)) as c:
        verify_forecast_schema(c)
        assert c.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        tables = [r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        return {t: sorted(c.execute(f"SELECT * FROM {t}").fetchall(), key=repr)
                for t in tables}


def test_committed_wal_and_complete_roundtrip(live,tmp_path):
    a = api()
    c, source = live
    wal = Path(str(source)+"-wal")
    assert wal.stat().st_size > 0
    before = read_payload(source)
    backup = tmp_path / "backup.sqlite"
    restored = tmp_path / "restored.sqlite"
    assert a.backup_database(source,backup) == backup
    assert a.restore_database(backup,restored) == restored
    assert read_payload(backup) == read_payload(restored) == before
    assert not Path(str(backup)+"-wal").exists()
    assert not Path(str(restored)+"-wal").exists()
    with closing(open_reader(restored)) as r:
        history = f.list_prediction_history(r,"SYN-m")
        assert history[0]["commitment_digest"] == "f"*64
        assert history[0]["evaluations"][0]["result_id"] == "SYN-r"


def test_uncommitted_writer_excluded(live,tmp_path):
    a = api()
    c, source = live
    before = read_payload(source)
    c.execute("BEGIN IMMEDIATE")
    i.put_player(c,i.Player("SYN-uncommitted"))
    try:
        out = a.backup_database(source,tmp_path/"snapshot.sqlite")
        assert read_payload(out) == before
        assert c.in_transaction
    finally:
        c.rollback()


def test_restore_preserves_source_and_backup(live,tmp_path):
    a = api()
    _,source = live
    original = read_payload(source)
    backup = a.backup_database(source,tmp_path/"backup.sqlite")
    saved = backup.read_bytes()
    restored = a.restore_database(backup,tmp_path/"restored.sqlite")
    with closing(open_writer(restored)) as c:
        c.execute("BEGIN IMMEDIATE")
        i.put_player(c,i.Player("SYN-restored-only"))
        c.commit()
    assert backup.read_bytes() == saved
    assert read_payload(source) == original
    assert read_payload(backup) == original


@pytest.mark.parametrize("operation", ["backup_database","restore_database"])
def test_existing_destination_unchanged(live,tmp_path,operation):
    a = api()
    _,source = live
    target = tmp_path/"existing.sqlite"
    target.write_bytes(b"existing-file")
    with pytest.raises(FileExistsError):
        getattr(a,operation)(source,target)
    assert target.read_bytes() == b"existing-file"


@pytest.mark.parametrize("operation", ["backup_database","restore_database"])
def test_same_path_rejected_without_source_change(live,operation):
    a = api()
    _,source = live
    before = read_payload(source)
    with pytest.raises((ValueError,FileExistsError)):
        getattr(a,operation)(source,source)
    assert read_payload(source) == before


@pytest.mark.parametrize("operation", ["backup_database","restore_database"])
def test_corrupt_input_leaves_no_destination_or_staging(tmp_path,operation):
    a = api()
    source = tmp_path/"corrupt.sqlite"
    source.write_bytes(b"not a sqlite file")
    destination = tmp_path/"destination.sqlite"
    before = set(tmp_path.iterdir())
    with pytest.raises((ValueError,sqlite3.DatabaseError)):
        getattr(a,operation)(source,destination)
    assert set(tmp_path.iterdir()) == before
    assert source.read_bytes() == b"not a sqlite file"


def test_unsupported_schema_rejected(tmp_path):
    a = api()
    source = tmp_path/"old.sqlite"
    with closing(open_writer(source)) as c:
        migrate(c)
    before = set(tmp_path.iterdir())
    original_bytes = source.read_bytes()
    destination = tmp_path/"backup.sqlite"
    with pytest.raises(ValueError, match="unrecognized forecast schema"):
        a.backup_database(source,destination)
    # SQLite may create its own source WAL/SHM even for mode=ro.
    # Do not unlink them: another connection could be using them.
    allowed_source_sidecars = {Path(str(source)+suffix)
                               for suffix in ("-wal", "-shm")}
    after = set(tmp_path.iterdir())
    assert before <= after <= before | allowed_source_sidecars
    assert not destination.exists()
    assert source.read_bytes() == original_bytes
    with closing(open_reader(source)) as reader:
        assert reader.execute("PRAGMA user_version").fetchone()[0] == 1
        assert reader.execute("SELECT id, marker FROM atp_lab_schema").fetchall() == [
            (1,"S2_BOOTSTRAP_V1")]


def test_schema_damage_rejected(live,tmp_path):
    a = api()
    c,source = live
    c.execute("DROP TRIGGER immutable_predictions_update")
    with pytest.raises(ValueError):
        a.backup_database(source,tmp_path/"backup.sqlite")
    assert not (tmp_path/"backup.sqlite").exists()


def test_foreign_key_corruption_rejected(live,tmp_path):
    a = api()
    c,source = live
    c.execute("PRAGMA foreign_keys=OFF")
    c.execute("INSERT INTO player_aliases VALUES ('SYN-feed','bad','SYN-missing')")
    with pytest.raises(ValueError):
        a.backup_database(source,tmp_path/"backup.sqlite")
    assert not (tmp_path/"backup.sqlite").exists()


def test_missing_source_does_not_create_files(tmp_path):
    a = api()
    with pytest.raises((FileNotFoundError,sqlite3.OperationalError)):
        a.backup_database(tmp_path/"missing.sqlite",tmp_path/"backup.sqlite")
    assert list(tmp_path.iterdir()) == []


def test_destination_sidecar_conflict_rejected(live,tmp_path):
    a = api()
    _,source = live
    dest = tmp_path/"backup.sqlite"
    sidecar = Path(str(dest)+"-wal")
    sidecar.write_bytes(b"unrelated")
    with pytest.raises(FileExistsError):
        a.backup_database(source,dest)
    assert not dest.exists()
    assert sidecar.read_bytes() == b"unrelated"


def test_reader_snapshot_stable_across_new_commits(live,tmp_path):
    a = api()
    c,source = live
    with closing(open_reader(source)) as reader:
        reader.execute("BEGIN")
        before = reader.execute("SELECT count(*) FROM players").fetchone()[0]
        c.execute("BEGIN IMMEDIATE")
        i.put_player(c,i.Player("SYN-next"))
        c.commit()
        out = a.backup_database(source,tmp_path/"snapshot.sqlite")
        assert reader.execute("SELECT count(*) FROM players").fetchone()[0] == before
        with closing(open_reader(out)) as r:
            assert r.execute("SELECT count(*) FROM players").fetchone()[0] == before+1
        reader.rollback()
