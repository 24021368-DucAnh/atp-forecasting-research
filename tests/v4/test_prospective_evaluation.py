"""S5 end-to-end synthetic commitment, evaluation and fixed cohort contracts."""
from contextlib import closing
from dataclasses import replace
from datetime import date
from hashlib import sha256
import json
import math
import sqlite3

import pytest

from atp_lab.database import identity as i, forecast as f
from atp_lab.database.connection import open_reader, open_writer
from atp_lab.database.migrations import migrate
from atp_lab.prediction import inference
from atp_lab.ingestion import adapter, pipeline

EARLY = "2025-05-01T12:00:00Z"
OBS = "2025-06-28T12:00:00Z"
READY = "2025-06-28T13:00:00Z"
REGISTER = "2025-06-29T11:00:00Z"
COMMIT = "2025-06-29T12:00:00Z"
END_WINDOW = "2025-06-30T13:00:00Z"
START = "2025-06-30T14:00:00Z"
PUBLISHED = "2025-06-30T16:00:00Z"
ROBS = "2025-06-30T17:00:00Z"
RREADY = "2025-06-30T18:00:00Z"
ASOF = "2025-06-30T19:00:00Z"
CORRECT = "2025-07-01T10:00:00Z"
LATER = "2025-07-01T12:00:00Z"
DIGEST = sha256(b"synthetic").hexdigest()
MODEL = inference.MODEL_ID
OTHER = "SYN-other-model"


def upgrade(c):
    from atp_lab.database.schema_v4 import migrate_evaluation
    return migrate_evaluation(c)


def commitment():
    from atp_lab.prediction import commitment
    return commitment


def service():
    from atp_lab.evaluation import service
    return service


def metric_api():
    from atp_lab.evaluation import metrics
    return metrics


def events():
    return (inference.EventMetadata("SYN-event",1,date(2025,6,30),EARLY,EARLY),
            inference.EventMetadata("SYN-old",1,date(2025,6,1),EARLY,EARLY))


@pytest.fixture
def db(tmp_path):
    path = tmp_path/"prospective.sqlite"
    with closing(open_writer(path)) as c:
        migrate(c)
        i.migrate_identity(c)
        f.migrate_forecast(c)
        c.execute("BEGIN IMMEDIATE")
        for source in ("SYN-feed","SYN-other"):
            i.put_source(c,i.Source(source,"SYNTHETIC","LOCKED"))
        for alias,player in (("a","SYN-A"),("b","SYN-B"),("c","SYN-C")):
            i.put_player(c,i.Player(player))
            i.put_alias(c,i.PlayerAlias("SYN-feed",alias,player))
        i.put_tournament(c,i.Tournament("SYN-event","SYN-event","2025","ATP250","HARD"))
        i.put_tournament(c,i.Tournament("SYN-old","SYN-old","2025","ATP500","CLAY"))
        for n,a,b in ((1,"SYN-A","SYN-B"),(2,"SYN-A","SYN-C"),(3,"SYN-B","SYN-C")):
            i.put_match(c,i.Match(f"SYN-m{n}","SYN-event",a,b))
            i.put_match_alias(c,i.MatchAlias("SYN-feed",f"m{n}",f"SYN-m{n}"))
            i.put_snapshot(c,i.Snapshot(f"SYN-fsnap{n}","SYN-feed",DIGEST,OBS))
            i.append_fixture(c,i.Fixture(f"SYN-f{n}",f"SYN-m{n}",1,"SYN-feed",
                f"SYN-fsnap{n}",a,b,OBS,READY,START,"SCHEDULED"))
        i.put_match(c,i.Match("SYN-history","SYN-old","SYN-A","SYN-C"))
        i.put_snapshot(c,i.Snapshot("SYN-hsnap","SYN-feed",DIGEST,"2025-06-03T12:00:00Z"))
        i.append_result(c,i.Result("SYN-h","SYN-history",1,"SYN-feed","SYN-hsnap",
            "2025-06-03T12:00:00Z","2025-06-03T13:00:00Z",
            "2025-06-02T16:00:00Z","2025-06-02T14:00:00Z","COMPLETED","SYN-A"))
        baseline = inference.synthetic_model_version(created_at=EARLY)
        f.append_model(c,baseline)
        f.append_model(c,replace(baseline,model_id=OTHER))
        c.commit()
        yield c,path


def counts(c):
    return tuple(c.execute(f"SELECT count(*) FROM {table}").fetchone()[0] for table in
                 ("feature_snapshots","predictions","prediction_receipts",
                  "evaluations","assessment_receipts","evaluation_cohorts"))


def commit(c,fixture="SYN-f1",**changes):
    args = dict(cutoff=COMMIT,created_at=COMMIT,model_id=MODEL)
    args.update(changes)
    return commitment().commit_prediction(c,fixture,events(),**args)


def cohort(c,fixtures=("SYN-f1","SYN-f2","SYN-f3"),models=(MODEL,),**changes):
    args = dict(registered_at=REGISTER,cutoff_end=END_WINDOW)
    args.update(changes)
    return service().register_cohort(c,"SYN-cohort",fixtures,models,**args)


def evaluate(c,p,as_of=ASOF):
    return service().evaluate_prediction(c,p.prediction.prediction_id,as_of=as_of)


def report(c,as_of=ASOF):
    return service().evaluation_report(c,"SYN-cohort",as_of=as_of)


def result(c,*,revision=1,source="SYN-feed",observed=ROBS,available=RREADY,
           actual=START,published=PUBLISHED,state="COMPLETED",winner="SYN-A"):
    key = f"SYN-result-{source}-{revision}"
    c.execute("BEGIN IMMEDIATE")
    i.put_snapshot(c,i.Snapshot(key+"-snap",source,DIGEST,observed))
    i.append_result(c,i.Result(key,"SYN-m1",revision,source,key+"-snap",
                               observed,available,published,actual,state,winner))
    c.commit()
    return key


def revise(c,*,state="CANCELLED",observed="2025-06-30T12:00:00Z",
           available="2025-06-30T12:01:00Z",scheduled=None,source="SYN-feed"):
    c.execute("BEGIN IMMEDIATE")
    i.put_snapshot(c,i.Snapshot("SYN-new-snap",source,DIGEST,observed))
    i.append_fixture(c,i.Fixture("SYN-new","SYN-m1",2,source,"SYN-new-snap",
        "SYN-A","SYN-B",observed,available,scheduled,state))
    c.commit()


def test_exact_v4_migration_preserves_v3_and_backup(db,tmp_path):
    from atp_lab.database.backup import backup_database, restore_database
    from atp_lab.database.schema_v3 import verify_forecast_schema
    c,path = db
    before = c.execute("SELECT * FROM fixture_versions ORDER BY fixture_id").fetchall()
    assert upgrade(c) == 4 == upgrade(c)
    verify_forecast_schema(c)
    assert c.execute("PRAGMA user_version").fetchone()[0] == 4
    assert c.execute("SELECT * FROM fixture_versions ORDER BY fixture_id").fetchall() == before
    p = commit(c)
    out = restore_database(backup_database(path,tmp_path/"backup.sqlite"),tmp_path/"restore.sqlite")
    with closing(open_reader(out)) as reader:
        verify_forecast_schema(reader)
        assert commitment().get_commitment(reader,p.prediction.prediction_id) == p
        assert counts(reader) == (1,1,1,0,0,0)


def test_v4_migration_rejects_damaged_v3_without_change(db):
    c,_ = db
    c.execute("DROP TRIGGER immutable_predictions_update")
    with pytest.raises(ValueError):
        upgrade(c)
    assert c.execute("PRAGMA user_version").fetchone()[0] == 3
    assert not c.execute("SELECT 1 FROM sqlite_master WHERE name='prediction_receipts'").fetchone()


def test_commit_atomic_replay_restart_and_read_only_preview(db):
    c,path = db
    upgrade(c)
    p = commit(c)
    assert p.prediction.probability_a > .5
    payload = json.loads(p.receipt_json)
    assert payload["features"]["result_ids"] == ["SYN-h"]
    assert len(payload["features"]["values"]) == 18
    assert payload["model"]["model_id"] == MODEL
    assert {x["tournament_id"] for x in payload["events"]} == {"SYN-event","SYN-old"}
    assert sha256(p.receipt_json.encode()).hexdigest() == p.prediction.commitment_digest
    assert p.feature.feature_digest == payload["features"]["digest"]
    assert counts(c) == (1,1,1,0,0,0)
    assert commit(c,cutoff="2025-06-29T19:00:00+07:00") == p
    with closing(open_writer(path)) as reopened:
        assert commit(reopened) == p
        assert counts(reopened) == (1,1,1,0,0,0)
    with closing(open_reader(path)) as reader:
        assert inference.predict_fixture(reader,"SYN-f1",events(),cutoff=COMMIT).probability_a == p.prediction.probability_a
        assert not reader.in_transaction


@pytest.mark.parametrize("change",[
    {"created_at":"2025-06-29T12:00:01Z"},
    {"cutoff":START,"created_at":START},
    {"cutoff":"2025-06-30T14:00:01Z","created_at":"2025-06-30T14:00:01Z"},
    {"model_id":OTHER},
    {"cutoff":"2025-06-29T12:00:00"},
])
def test_invalid_commit_has_no_partial_rows(db,change):
    c,_ = db
    upgrade(c)
    with pytest.raises(ValueError):
        commit(c,**change)
    assert counts(c) == (0,0,0,0,0,0)
    assert not c.in_transaction


def test_backdated_new_commit_after_result_exists_rejected(db):
    c,_ = db
    upgrade(c)
    result(c)
    with pytest.raises(ValueError):
        commit(c)
    assert counts(c) == (0,0,0,0,0,0)


def test_backdated_commit_after_new_fixture_rejected(db):
    c,_ = db
    upgrade(c)
    revise(c)
    with pytest.raises(ValueError):
        commit(c)
    assert counts(c) == (0,0,0,0,0,0)


def test_commit_replay_after_result_keeps_original(db):
    c,_ = db
    upgrade(c)
    p = commit(c)
    result(c)
    assert commit(c) == p
    assert counts(c) == (1,1,1,0,0,0)


def test_same_fixture_model_different_commit_conflicts(db):
    c,_ = db
    upgrade(c)
    p = commit(c)
    with pytest.raises(ValueError):
        commit(c,cutoff="2025-06-29T12:01:00Z",created_at="2025-06-29T12:01:00Z")
    assert commitment().get_commitment(c,p.prediction.prediction_id) == p
    assert counts(c) == (1,1,1,0,0,0)


def test_failed_prediction_insert_rolls_back_feature_and_receipt(db):
    c,_ = db
    upgrade(c)
    def authorize(action,arg1,arg2,dbname,trigger):
        if action == sqlite3.SQLITE_INSERT and arg1 == "predictions":
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
    c.set_authorizer(authorize)
    try:
        with pytest.raises(sqlite3.DatabaseError):
            commit(c)
    finally:
        c.set_authorizer(None)
    assert counts(c) == (0,0,0,0,0,0)
    assert not c.in_transaction


def test_caller_transaction_is_not_consumed(db):
    c,_ = db
    upgrade(c)
    c.execute("BEGIN IMMEDIATE")
    with pytest.raises(ValueError):
        commit(c)
    assert c.in_transaction
    c.rollback()
    assert counts(c) == (0,0,0,0,0,0)


def test_corrupt_v4_schema_blocks_commit(db):
    c,_ = db
    upgrade(c)
    c.execute("DROP TRIGGER immutable_prediction_receipts_update")
    with pytest.raises(ValueError):
        commit(c)
    assert counts(c) == (0,0,0,0,0,0)


def test_revisions_fixed_denominator_and_asof_metrics(db):
    c,path = db
    upgrade(c)
    fixed = cohort(c,models=(MODEL,OTHER))
    p = commit(c)
    commit(c,"SYN-f2")
    assert evaluate(c,p).reason == "NO_RESULT"
    first_id = result(c)
    first = evaluate(c,p)
    assert (first.status,first.reason,first.result_id,first.outcome_a) == ("RECORDED","ELIGIBLE",first_id,1)
    assert evaluate(c,p) == first
    initial = report(c)["models"][MODEL]
    assert (initial["target_n"],initial["committed_n"],initial["scored_n"]) == (3,2,1)
    assert initial["status_counts"] == {"INELIGIBLE":0,"MISSING":1,"PENDING":1,"RECORDED":1,"VOID":0}
    assert initial["metrics"]["accuracy"] == 1.0
    assert initial["prediction_coverage"] == pytest.approx(2/3)
    assert initial["scored_coverage"] == pytest.approx(1/3)
    assert report(c)["models"][OTHER]["committed_n"] == 0
    assert report(c)["matched"]["matched_n"] == 0
    second_id = result(c,revision=2,observed=CORRECT,available=CORRECT,winner="SYN-B")
    assert report(c,LATER)["models"][MODEL]["scored_n"] == 0
    second = evaluate(c,p,LATER)
    assert (second.status,second.result_id,second.outcome_a) == ("RECORDED",second_id,0)
    assert second.evaluation_id != first.evaluation_id
    after = report(c,LATER)["models"][MODEL]
    assert after["metrics"]["accuracy"] == 0.0
    assert after["target_n"] == 3 and after["scored_n"] == 1
    assert report(c)["models"][MODEL] == initial
    assert counts(c) == (2,2,2,2,2,1)
    assert cohort(c,fixtures=("SYN-f3","SYN-f1","SYN-f2"),models=(OTHER,MODEL)) == fixed
    with closing(open_reader(path)) as reader:
        assert report(reader,LATER) == report(c,LATER)
        assert not reader.in_transaction
        assert commitment().get_commitment(reader,p.prediction.prediction_id) == p


@pytest.mark.parametrize("change,reason",[
    ({"available":None},"RESULT_UNAVAILABLE"),
    ({"available":"2025-07-01T12:00:00Z"},"RESULT_UNAVAILABLE"),
    ({"observed":"2025-07-01T10:00:00Z","available":"2025-07-01T10:00:00Z"},"NO_RESULT"),
])
def test_unavailable_or_future_result_no_assessment(db,change,reason):
    c,_ = db
    upgrade(c)
    p = commit(c)
    result(c,**change)
    decision = evaluate(c,p)
    assert (decision.status,decision.reason,decision.outcome_a) == ("PENDING",reason,None)
    assert counts(c) == (1,1,1,0,0,0)


def test_unavailable_latest_blocks_old_assessment(db):
    c,_ = db
    upgrade(c)
    cohort(c,fixtures=("SYN-f1",))
    p = commit(c)
    result(c)
    assert evaluate(c,p).status == "RECORDED"
    result(c,revision=2,observed=CORRECT,available=None,winner="SYN-B")
    assert evaluate(c,p,LATER).reason == "RESULT_UNAVAILABLE"
    assert report(c,LATER)["models"][MODEL]["scored_n"] == 0
    assert report(c)["models"][MODEL]["scored_n"] == 1
    assert counts(c) == (1,1,1,1,1,1)


@pytest.mark.parametrize("change,status,reason",[
    ({"actual":None},"INELIGIBLE","UNVERIFIED_TIMING"),
    ({"published":None},"INELIGIBLE","UNVERIFIED_TIMING"),
    ({"actual":COMMIT},"INELIGIBLE","LATE_PREDICTION"),
    ({"actual":"2025-06-29T11:00:00Z"},"INELIGIBLE","LATE_PREDICTION"),
    ({"state":"VOID","winner":None},"VOID","VOID_RESULT"),
    ({"state":"WALKOVER"},"VOID","WALKOVER"),
    ({"state":"RETIRED"},"INELIGIBLE","RETIRED"),
    ({"state":"UNKNOWN","winner":None},"INELIGIBLE","UNKNOWN_RESULT"),
])
def test_terminal_exclusions_are_explicit_and_unscored(db,change,status,reason):
    c,_ = db
    upgrade(c)
    cohort(c,fixtures=("SYN-f1",))
    p = commit(c)
    result(c,**change)
    a = evaluate(c,p)
    assert (a.status,a.reason,a.outcome_a) == (status,reason,None)
    assert a == evaluate(c,p)
    model = report(c)["models"][MODEL]
    assert model["target_n"] == 1 and model["scored_n"] == 0
    assert model["reason_counts"] == {reason:1}
    assert model["metrics"]["accuracy"] is None
    assert counts(c) == (1,1,1,1,1,1)


def test_cross_source_result_never_scores(db):
    c,_ = db
    upgrade(c)
    p = commit(c)
    result(c,source="SYN-other")
    a = evaluate(c,p)
    assert (a.status,a.reason,a.outcome_a) == ("INELIGIBLE","RESULT_SOURCE_MISMATCH",None)


def test_multi_source_correction_blocks_score(db):
    c,_ = db
    upgrade(c)
    cohort(c,fixtures=("SYN-f1",))
    p = commit(c)
    result(c)
    assert evaluate(c,p).status == "RECORDED"
    result(c,source="SYN-other",observed=CORRECT,available=CORRECT)
    assert evaluate(c,p,LATER).reason == "AMBIGUOUS_RESULT_SOURCE"
    assert report(c,LATER)["models"][MODEL]["scored_n"] == 0


@pytest.mark.parametrize("state,scheduled",[("CANCELLED",None),("SCHEDULED","2025-06-30T15:00:00Z")])
def test_fixture_superseded_between_commit_and_start_excluded(db,state,scheduled):
    c,_ = db
    upgrade(c)
    p = commit(c)
    revise(c,state=state,scheduled=scheduled)
    result(c)
    assert evaluate(c,p).reason == "FIXTURE_SUPERSEDED"
    assert commitment().get_commitment(c,p.prediction.prediction_id) == p


def test_assessment_created_later_not_visible_in_prior_report(db):
    c,_ = db
    upgrade(c)
    cohort(c,fixtures=("SYN-f1",))
    p = commit(c)
    result(c)
    evaluate(c,p,LATER)
    assert report(c)["models"][MODEL]["reason_counts"] == {"NOT_EVALUATED":1}
    assert report(c,LATER)["models"][MODEL]["scored_n"] == 1


@pytest.mark.parametrize("fixtures,models",[
    (("SYN-f1","SYN-f1"),(MODEL,)),
    (("SYN-missing",),(MODEL,)),
    (("SYN-f1",),("SYN-missing",)),
    (("SYN-f1",),(MODEL,MODEL)),
    ((),(MODEL,)),
    (("SYN-f1",),()),
])
def test_invalid_cohort_no_write(db,fixtures,models):
    c,_ = db
    upgrade(c)
    with pytest.raises(ValueError):
        cohort(c,fixtures,models)
    assert counts(c) == (0,0,0,0,0,0)


def test_cohort_cannot_be_registered_after_result_or_changed(db):
    c,_ = db
    upgrade(c)
    cohort(c,fixtures=("SYN-f1",))
    with pytest.raises(ValueError):
        cohort(c,fixtures=("SYN-f1","SYN-f2"))
    result(c)
    with pytest.raises(ValueError):
        service().register_cohort(c,"SYN-late",("SYN-f1",),(MODEL,),
                                  registered_at=REGISTER,cutoff_end=END_WINDOW)
    assert counts(c)[-1] == 1


def test_cohort_groups_and_outside_window_no_score(db):
    c,_ = db
    upgrade(c)
    cohort(c,fixtures=("SYN-f1",),registered_at="2025-06-29T12:01:00Z")
    p = commit(c)
    result(c)
    evaluate(c,p)
    model = report(c)["models"][MODEL]
    assert model["target_n"] == 1 and model["scored_n"] == 0
    assert model["reason_counts"] == {"OUTSIDE_COHORT_WINDOW":1}
    assert model["groups"]["tier"]["ATP250"]["target_n"] == 1
    assert model["groups"]["surface"]["HARD"]["target_n"] == 1
    assert model["groups"]["month"]["2025-06"]["target_n"] == 1


def test_sidecars_and_cohort_are_immutable(db):
    c,_ = db
    upgrade(c)
    cohort(c,fixtures=("SYN-f1",))
    p = commit(c)
    result(c)
    evaluate(c,p)
    for table in ("prediction_receipts","assessment_receipts","evaluation_cohorts"):
        with pytest.raises(sqlite3.IntegrityError):
            c.execute(f"DELETE FROM {table}")
    assert counts(c) == (1,1,1,1,1,1)


def test_legacy_prediction_without_commit_receipt_not_scored(db):
    c,_ = db
    upgrade(c)
    cohort(c,fixtures=("SYN-f1",))
    c.execute("BEGIN IMMEDIATE")
    f.append_feature(c,f.FeatureSnapshot("SYN-legacy-f","SYN-f1",DIGEST,COMMIT))
    f.append_prediction(c,f.Prediction("SYN-legacy-p","SYN-m1","SYN-f1",
                                      "SYN-legacy-f",MODEL,COMMIT,.7,DIGEST))
    c.commit()
    result(c)
    with pytest.raises(ValueError):
        service().evaluate_prediction(c,"SYN-legacy-p",as_of=ASOF)
    model = report(c)["models"][MODEL]
    assert model["committed_n"] == model["scored_n"] == 0
    assert model["reason_counts"] == {"UNVERIFIED_COMMITMENT":1}


def test_ingestion_commit_evaluate_restart_backup_roundtrip(db,tmp_path):
    from atp_lab.database.backup import backup_database, restore_database
    c,path = db
    upgrade(c)
    cohort(c,fixtures=("SYN-f1",))
    p = commit(c)
    class Fake:
        def fetch(self,url):
            assert not c.in_transaction
            assert url == adapter.RESULTS_ENDPOINT
            return json.dumps({"results":[{
                "match_id":"m1","player_1":"b","player_2":"a","revision":1,
                "published_at":PUBLISHED,"actual_start":START,"state":"COMPLETED","winner":"a"
            }]}).encode()
    r = pipeline.ingest_batch(c,adapter.SourcePolicy("SYN-feed",enabled=True),
        adapter.RESULTS_ENDPOINT,Fake(),job_id="SYN-prospective-job",
        started_at=PUBLISHED,observed_at=ROBS,available_at=RREADY,ended_at=ASOF,
        sleep=lambda _: None)
    assert r.status == "SUCCEEDED" and r.inserted == 1
    assessment = evaluate(c,p)
    assert assessment.status == "RECORDED"
    with closing(open_writer(path)) as again:
        assert evaluate(again,p) == assessment
    dest = restore_database(backup_database(path,tmp_path/"prospective-backup.sqlite"),
                            tmp_path/"prospective-restore.sqlite")
    with closing(open_reader(dest)) as reader:
        assert report(reader) == report(c)
        assert commitment().get_commitment(reader,p.prediction.prediction_id) == p


def test_metric_literal_values_and_tie_a():
    m = metric_api().score_metrics(((.8,1),(.3,0),(.5,1)))
    assert m.n == 3 and m.accuracy == 1.0
    assert m.brier == pytest.approx(.38/3)
    assert m.log_loss == pytest.approx((-math.log(.8)-math.log(.7)-math.log(.5))/3)
    assert m.ece == pytest.approx(1/3)
    assert len(m.bins) == 10 and sum(x.n for x in m.bins) == 3


def test_metric_boundaries_empty_and_finite():
    a = metric_api()
    m = a.score_metrics(((0.,1),(1.,0)))
    assert m.brier == 1. and m.accuracy == 0.
    assert math.isfinite(m.log_loss) and m.log_loss > 27
    assert m.bins[0].n == m.bins[9].n == 1
    empty = a.score_metrics(())
    assert empty.n == 0 and empty.accuracy is None and empty.brier is None
    assert empty.log_loss is None and empty.ece is None


@pytest.mark.parametrize("row",[(float("nan"),1),(float("inf"),1),(-.1,0),(1.1,1),(True,1),(.5,True),(.5,2)])
def test_metric_rejects_invalid_observation(row):
    with pytest.raises(ValueError):
        metric_api().score_metrics((row,))


def test_matched_keys_require_same_outcome_revision():
    out = metric_api().matched_metrics({
        "SYN-model-a":{"SYN-f1":(.8,1,"SYN-r1"),"SYN-f2":(.6,1,"SYN-r2"),
                       "SYN-f3":(.4,0,"SYN-r3")},
        "SYN-model-b":{"SYN-f1":(.4,1,"SYN-r1"),"SYN-f2":(.8,0,"SYN-r2-new"),
                       "SYN-f4":(.3,0,"SYN-r4")},
    })
    assert out["matched_keys"] == ("SYN-f1",) and out["matched_n"] == 1
    assert out["models"]["SYN-model-a"]["accuracy"] == 1.
    assert out["models"]["SYN-model-b"]["accuracy"] == 0.
