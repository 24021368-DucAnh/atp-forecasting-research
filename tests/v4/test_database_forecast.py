"""S2.3: synthetic forecast lineage, no fitting or settlement."""
from contextlib import closing
from dataclasses import replace
import sqlite3

import pytest

from atp_lab.database import identity as i
from atp_lab.database.connection import open_reader, open_writer
from atp_lab.database.migrations import migrate

OBS = "2026-01-01T08:00:00Z"
READY = "2026-01-01T09:00:00Z"
START = "2026-01-02T10:00:00Z"
DONE = "2026-01-02T12:00:00Z"
AFTER = "2026-01-02T13:00:00Z"


def api():
    from atp_lab.database import forecast
    return forecast


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "forecast.sqlite"
    with closing(open_writer(path)) as c:
        migrate(c)
        i.migrate_identity(c)
        c.execute("BEGIN IMMEDIATE")
        i.put_source(c, i.Source("SYN-feed", "SYNTHETIC", "LOCKED"))
        i.put_snapshot(c, i.Snapshot("SYN-s1", "SYN-feed", "a"*64, OBS))
        i.put_snapshot(c, i.Snapshot("SYN-s2", "SYN-feed", "b"*64, DONE))
        for p in ("SYN-A", "SYN-B", "SYN-C"):
            i.put_player(c, i.Player(p))
        i.put_tournament(c, i.Tournament("SYN-t", "SYN-event", "2026", "ATP250", "HARD"))
        for m, b in (("SYN-m1","SYN-B"), ("SYN-m2","SYN-C")):
            i.put_match(c, i.Match(m,"SYN-t","SYN-A",b))
            i.append_fixture(c, i.Fixture(m+"-f",m,1,"SYN-feed","SYN-s1","SYN-A",b,OBS,READY,START,"SCHEDULED"))
            i.append_result(c, i.Result(m+"-r",m,1,"SYN-feed","SYN-s2",DONE,DONE,DONE,START,"COMPLETED","SYN-A"))
        c.commit()
        yield c, path


def initialize(db):
    a = api()
    c, _ = db
    a.migrate_forecast(c)
    c.execute("BEGIN IMMEDIATE")
    a.append_feature(c, a.FeatureSnapshot("SYN-feature","SYN-m1-f","c"*64,READY))
    a.append_feature(c, a.FeatureSnapshot("SYN-feature2","SYN-m2-f","d"*64,READY))
    a.append_model(c, a.ModelVersion("SYN-model","e"*64,"f"*64,OBS,READY,"SYNTHETIC"))
    c.commit()
    return a, c


def prediction(a, **kwargs):
    return replace(a.Prediction("SYN-p1","SYN-m1","SYN-m1-f","SYN-feature",
                                "SYN-model",READY,0.65,"1"*64), **kwargs)


def evaluation(a, **kwargs):
    return replace(a.Evaluation("SYN-e1","SYN-p1","SYN-m1-r",AFTER,"RECORDED"), **kwargs)


def test_v2_to_v3_preserves_rows_and_is_idempotent(db):
    a = api()
    c, _ = db
    before = c.execute("SELECT * FROM fixture_versions ORDER BY fixture_id").fetchall()
    assert a.migrate_forecast(c) == 3
    assert c.execute("PRAGMA user_version").fetchone()[0] == 3
    assert a.migrate_forecast(c) == 3
    assert c.execute("SELECT * FROM fixture_versions ORDER BY fixture_id").fetchall() == before
    assert {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")} >= {
        "feature_snapshots","model_versions","predictions","evaluations","job_runs","data_quality_issues"}
    assert c.execute("PRAGMA foreign_key_check").fetchall() == []


def test_damaged_v2_rejected_without_upgrade(db):
    a = api()
    c, _ = db
    c.execute("DROP TRIGGER immutable_fixture_versions_update")
    with pytest.raises(ValueError):
        a.migrate_forecast(c)
    assert c.execute("PRAGMA user_version").fetchone()[0] == 2


def test_damaged_v3_rejected(db):
    a, c = initialize(db)
    c.execute("DROP TRIGGER immutable_predictions_update")
    with pytest.raises(ValueError):
        a.migrate_forecast(c)
    assert c.execute("PRAGMA user_version").fetchone()[0] == 3


def test_identity_writer_still_works_after_upgrade(db):
    a, c = initialize(db)
    c.execute("BEGIN IMMEDIATE")
    assert i.put_player(c, i.Player("SYN-D")) is True
    c.commit()
    assert c.execute("SELECT count(*) FROM players").fetchone()[0] == 4


def test_forecast_lineage_round_trip_read_only(db):
    a, c = initialize(db)
    c.execute("BEGIN IMMEDIATE")
    a.append_prediction(c, prediction(a))
    a.append_evaluation(c, evaluation(a))
    c.commit()
    with closing(open_reader(db[1])) as reader:
        history = a.list_prediction_history(reader, "SYN-m1")
        assert len(history) == 1
        row = history[0]
        assert (row["prediction_id"], row["fixture_id"], row["feature_id"], row["model_id"]) == (
            "SYN-p1","SYN-m1-f","SYN-feature","SYN-model")
        assert row["probability_a"] == pytest.approx(.65)
        assert row["commitment_digest"] == "1"*64
        assert row["evaluations"][0]["result_id"] == "SYN-m1-r"
        assert a.list_prediction_history(reader, "SYN-m2") == []


@pytest.mark.parametrize("change", [
    {"model_id":"SYN-missing"}, {"fixture_id":"SYN-missing"},
    {"feature_id":"SYN-missing"}, {"feature_id":"SYN-feature2"},
    {"match_id":"SYN-m2"},
])
def test_prediction_requires_exact_lineage(db, change):
    a, c = initialize(db)
    c.execute("BEGIN IMMEDIATE")
    with pytest.raises((ValueError,sqlite3.IntegrityError)):
        a.append_prediction(c, prediction(a, **change))
    c.rollback()
    assert c.execute("SELECT count(*) FROM predictions").fetchone()[0] == 0


def test_evaluation_cannot_bind_wrong_match(db):
    a, c = initialize(db)
    c.execute("BEGIN IMMEDIATE")
    a.append_prediction(c, prediction(a))
    with pytest.raises((ValueError,sqlite3.IntegrityError)):
        a.append_evaluation(c, evaluation(a,result_id="SYN-m2-r"))
    c.rollback()


@pytest.mark.parametrize("p", [-.01, 1.01, float("nan"), float("inf"), True, "0.65"])
def test_invalid_probability_rejected(db,p):
    a,c = initialize(db)
    c.execute("BEGIN IMMEDIATE")
    with pytest.raises(ValueError):
        a.append_prediction(c,prediction(a,probability_a=p))
    c.rollback()


@pytest.mark.parametrize("timestamp", ["2026-02-30T00:00:00Z","2026-01-01T09:00:00"])
def test_invalid_prediction_timestamp(db,timestamp):
    a,c = initialize(db)
    c.execute("BEGIN IMMEDIATE")
    with pytest.raises(ValueError):
        a.append_prediction(c,prediction(a,created_at=timestamp))
    c.rollback()


def test_prediction_replay_and_conflicting_duplicate(db):
    a,c = initialize(db)
    c.execute("BEGIN IMMEDIATE")
    p = prediction(a)
    assert a.append_prediction(c,p) is True
    assert a.append_prediction(c,p) is False
    with pytest.raises(ValueError):
        a.append_prediction(c,replace(p,probability_a=.7))
    c.commit()
    assert c.execute("SELECT probability_a FROM predictions").fetchall() == [(.65,)]


def test_new_id_cannot_replace_same_fixture_model_prediction(db):
    a,c = initialize(db)
    c.execute("BEGIN IMMEDIATE")
    a.append_prediction(c,prediction(a))
    with pytest.raises((ValueError,sqlite3.IntegrityError)):
        a.append_prediction(c,prediction(a,prediction_id="SYN-p2"))
    c.rollback()


def test_corrected_result_appends_evaluation(db):
    a,c = initialize(db)
    c.execute("BEGIN IMMEDIATE")
    a.append_prediction(c,prediction(a))
    a.append_evaluation(c,evaluation(a))
    i.append_result(c,i.Result("SYN-r2","SYN-m1",2,"SYN-feed","SYN-s2",AFTER,AFTER,DONE,START,"COMPLETED","SYN-B"))
    assert a.append_evaluation(c,evaluation(a,evaluation_id="SYN-e2",result_id="SYN-r2")) is True
    c.commit()
    rows = a.list_prediction_history(c,"SYN-m1")[0]["evaluations"]
    assert {r["result_id"] for r in rows} == {"SYN-m1-r","SYN-r2"}


def test_duplicate_assessment_different_id_rejected(db):
    a,c = initialize(db)
    c.execute("BEGIN IMMEDIATE")
    a.append_prediction(c,prediction(a))
    e = evaluation(a)
    assert a.append_evaluation(c,e) is True
    assert a.append_evaluation(c,e) is False
    with pytest.raises((ValueError,sqlite3.IntegrityError)):
        a.append_evaluation(c,replace(e,evaluation_id="SYN-other-e"))
    c.rollback()


@pytest.mark.parametrize("sql", [
    "UPDATE predictions SET probability_a=.9",
    "DELETE FROM predictions",
    "INSERT OR REPLACE INTO predictions SELECT * FROM predictions",
    "UPDATE evaluations SET status='VOID'",
    "DELETE FROM evaluations",
    "UPDATE model_versions SET scope='REAL'",
    "DELETE FROM feature_snapshots",
])
def test_append_only_database_guards(db,sql):
    a,c = initialize(db)
    c.execute("BEGIN IMMEDIATE")
    a.append_prediction(c,prediction(a))
    a.append_evaluation(c,evaluation(a))
    with pytest.raises(sqlite3.IntegrityError):
        c.execute(sql)
    c.rollback()


def test_model_scope_and_digest_must_be_synthetic(db):
    a,c = initialize(db)
    c.execute("BEGIN IMMEDIATE")
    for model in (
        a.ModelVersion("SYN-live","e"*64,"f"*64,OBS,READY,"REAL"),
        a.ModelVersion("SYN-bad","not-a-digest","f"*64,OBS,READY,"SYNTHETIC"),
    ):
        with pytest.raises((ValueError,sqlite3.IntegrityError)):
            a.append_model(c,model)
    c.rollback()


def test_job_and_quarantine_records_are_idempotent(db):
    a,c = initialize(db)
    c.execute("BEGIN IMMEDIATE")
    job = a.JobRun("SYN-job","INGEST",1,OBS,READY,"FAILED")
    issue = a.QualityIssue("SYN-q","SYN-feed",READY,"synthetic invalid payload")
    assert a.record_job(c,job) is True
    assert a.record_job(c,job) is False
    assert a.record_quality_issue(c,issue) is True
    assert a.record_quality_issue(c,issue) is False
    with pytest.raises(ValueError):
        a.record_job(c,replace(job,status="SUCCEEDED"))
    c.commit()
    assert c.execute("SELECT count(*) FROM job_runs").fetchone()[0] == 1
    assert c.execute("SELECT count(*) FROM data_quality_issues").fetchone()[0] == 1


def test_caller_rollback_and_no_implicit_write(db):
    a,c = initialize(db)
    with pytest.raises(ValueError):
        a.append_prediction(c,prediction(a))
    c.execute("BEGIN IMMEDIATE")
    a.append_prediction(c,prediction(a))
    a.append_evaluation(c,evaluation(a))
    c.rollback()
    assert c.execute("SELECT count(*) FROM predictions").fetchone()[0] == 0
    assert c.execute("SELECT count(*) FROM evaluations").fetchone()[0] == 0
