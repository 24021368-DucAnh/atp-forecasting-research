"""S6 contracts: synthetic-only chronological learning and manual lifecycle."""
from contextlib import closing
from dataclasses import asdict, replace
from datetime import date, timedelta
from hashlib import sha256
import json
import math
import sqlite3

import pytest

from atp_lab.database import identity as i, forecast as f
from atp_lab.database.connection import open_reader, open_writer
from atp_lab.database.migrations import migrate
from atp_lab.database.schema_v4 import migrate_evaluation
from atp_lab.prediction import commitment, inference
from atp_lab.prediction.features import FEATURE_NAMES
from atp_lab.evaluation import service

BASE = inference.MODEL_ID
CUTOFF = "2025-05-01T12:00:00Z"
FROZEN = "2025-05-02T12:00:00Z"
EVAL_START = "2025-05-03T00:00:00Z"
EVAL_END = "2025-05-31T00:00:00Z"
REPORT = "2025-06-01T12:00:00Z"
APPROVAL = "2025-06-02T12:00:00Z"
ROLLBACK = "2025-06-03T12:00:00Z"


def upgrade(conn):
    from atp_lab.database.schema_v5 import migrate_training
    return migrate_training(conn)


def api():
    from atp_lab.training import registry
    return registry


def proto_api():
    from atp_lab.training import protocol
    return protocol


def dataset_api():
    from atp_lab.training import dataset
    return dataset


def protocol(**changes):
    args = dict(protocol_id="SYN-protocol", registered_at="2025-04-30T12:00:00Z",
                fit_start="2025-01-01",fit_end="2025-02-01",
                calibration_start="2025-03-01",calibration_end="2025-04-01",
                training_cutoff=CUTOFF,evaluation_cohort_id="SYN-future-cohort",
                evaluation_start=EVAL_START,evaluation_end=EVAL_END,
                min_fit=4,min_calibration=4,min_matched=2)
    args.update(changes)
    return proto_api().TrainingProtocol(**args)


def stamp(day,hour=12):
    return f"{day.isoformat()}T{hour:02}:00:00Z"


class Lab:
    def __init__(self,c,path,root):
        self.c,self.path,self.root=c,path,root
        self.events=[]
        self.rows={}

    def fixture(self,key,day,pair=("SYN-A","SYN-B"),surface="HARD",tournament=None,revision=1,event_day=None):
        day=date.fromisoformat(day)
        tournament=tournament or f"SYN-t-{key}"
        fid,mid,snap=(f"SYN-{kind}-{key}" for kind in ("f","m","fs"))
        obs=stamp(day-timedelta(days=2),9)
        avail=stamp(day-timedelta(days=2),10)
        self.c.execute("BEGIN IMMEDIATE")
        if not self.c.execute("SELECT 1 FROM tournaments WHERE tournament_id=?",(tournament,)).fetchone():
            i.put_tournament(self.c,i.Tournament(tournament,tournament,"2025","ATP250",surface))
        i.put_match(self.c,i.Match(mid,tournament,*pair))
        i.put_snapshot(self.c,i.Snapshot(snap,"SYN-feed",sha256(key.encode()).hexdigest(),obs))
        i.append_fixture(self.c,i.Fixture(fid,mid,1,"SYN-feed",snap,*pair,obs,avail,
                                           stamp(day,14),"SCHEDULED"))
        self.c.commit()
        meta=stamp(day-timedelta(days=3),8)
        self.events.append(inference.EventMetadata(tournament,revision,date.fromisoformat(event_day) if event_day else day,meta,meta))
        self.rows[key]=(fid,mid,day,pair,tournament)
        return fid

    def commit(self,key,model_id=BASE,clock=None):
        fid,_,day,_,_=self.rows[key]
        clock=clock or stamp(day-timedelta(days=1))
        args=dict(cutoff=clock,created_at=clock,model_id=model_id)
        if model_id!=BASE:
            args["model_dir"]=self.root
        return commitment.commit_prediction(self.c,fid,tuple(self.events),**args)

    def result(self,key,*,outcome=1,revision=1,observed=None,available="auto",
               state="COMPLETED",actual="auto",published="auto"):
        _,mid,day,pair,_=self.rows[key]
        rid=f"SYN-r-{key}-{revision}"
        obs=observed or stamp(day,17)
        av=stamp(day,18) if available=="auto" else available
        ac=stamp(day,14) if actual=="auto" else actual
        pub=stamp(day,16) if published=="auto" else published
        winner=pair[0 if outcome else 1] if outcome is not None else None
        self.c.execute("BEGIN IMMEDIATE")
        i.put_snapshot(self.c,i.Snapshot(rid+"-snap","SYN-feed",sha256(rid.encode()).hexdigest(),obs))
        i.append_result(self.c,i.Result(rid,mid,revision,"SYN-feed",rid+"-snap",obs,av,
                                        pub,ac,state,winner))
        self.c.commit()
        return rid

    def evaluate(self,pred,key,as_of=None):
        day=self.rows[key][2]
        return service.evaluate_prediction(self.c,pred.prediction.prediction_id,
                                            as_of=as_of or stamp(day,19))

    def example(self,key,day,outcome,**changes):
        self.fixture(key,day,**changes)
        p=self.commit(key)
        self.result(key,outcome=outcome)
        assert self.evaluate(p,key).status=="RECORDED"
        return p


@pytest.fixture
def lab(tmp_path):
    path=tmp_path/"training.sqlite"
    root=tmp_path/"model_artifacts"
    root.mkdir()
    with closing(open_writer(path)) as c:
        migrate(c)
        i.migrate_identity(c)
        f.migrate_forecast(c)
        migrate_evaluation(c)
        c.execute("BEGIN IMMEDIATE")
        i.put_source(c,i.Source("SYN-feed","SYNTHETIC","LOCKED"))
        for name in ("SYN-A","SYN-B","SYN-C"):
            i.put_player(c,i.Player(name))
        f.append_model(c,inference.synthetic_model_version(created_at="2024-01-01T00:00:00Z"))
        c.commit()
        yield Lab(c,path,root)


def seed(lab,*,cal_labels=(1,0,1,0)):
    lab.fixture("history","2024-10-01",pair=("SYN-A","SYN-C"))
    lab.result("history",outcome=1)
    for j,(day,pair,surface,y) in enumerate(zip(
        ("2025-01-01","2025-01-03","2025-01-05","2025-01-07"),
        (("SYN-A","SYN-B"),("SYN-A","SYN-C"),("SYN-B","SYN-C"),("SYN-A","SYN-B")),
        ("HARD","CLAY","GRASS","HARD"),(1,0,1,0))):
        lab.example(f"fit{j}",day,y,pair=pair,surface=surface)
    for j,(day,y) in enumerate(zip(("2025-03-01","2025-03-03","2025-03-05","2025-03-07"),cal_labels)):
        lab.example(f"cal{j}",day,y,pair=("SYN-A","SYN-C"),surface="HARD")


@pytest.fixture
def prepared(lab):
    upgrade(lab.c)
    seed(lab)
    proto_api().register_protocol(lab.c,protocol())
    return lab


def train(lab,**changes):
    args=dict(created_at=FROZEN,model_dir=lab.root)
    args.update(changes)
    return api().train_candidate(lab.c,"SYN-protocol",**args)


@pytest.fixture
def trained(prepared):
    return prepared,train(prepared)


def dataset(lab):
    return dataset_api().collect_dataset(lab.c,"SYN-protocol")


def registry_counts(c):
    return tuple(c.execute(f"SELECT count(*) FROM {name}").fetchone()[0] for name in
                 ("training_protocols","candidate_artifacts","model_lifecycle_events","model_versions"))


def test_v5_migration_preserves_v4_receipt_and_backup(lab,tmp_path):
    from atp_lab.database.backup import backup_database, restore_database
    from atp_lab.database.schema_v3 import verify_forecast_schema
    p=lab.example("old","2025-01-01",1)
    before=service.evaluate_prediction(lab.c,p.prediction.prediction_id,as_of="2025-01-01T19:00:00Z")
    assert upgrade(lab.c)==4+1==upgrade(lab.c)
    verify_forecast_schema(lab.c)
    assert commitment.get_commitment(lab.c,p.prediction.prediction_id)==p
    assert lab.evaluate(p,"old")==before
    assert registry_counts(lab.c)==(0,0,0,1)
    backup=backup_database(lab.path,tmp_path/"v5-backup.sqlite")
    dest=restore_database(backup,tmp_path/"v5-restored.sqlite")
    with closing(open_reader(dest)) as reader:
        verify_forecast_schema(reader)
        assert commitment.get_commitment(reader,p.prediction.prediction_id)==p


def test_v5_partial_ddl_failure_is_atomic(lab):
    def authorize(action,arg1,arg2,db,trigger):
        if action==sqlite3.SQLITE_CREATE_TABLE and arg1=="candidate_artifacts":
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
    lab.c.set_authorizer(authorize)
    try:
        with pytest.raises(sqlite3.DatabaseError):
            upgrade(lab.c)
    finally:
        lab.c.set_authorizer(None)
    assert lab.c.execute("PRAGMA user_version").fetchone()[0]==4
    assert lab.c.execute("SELECT name FROM sqlite_master WHERE name='training_protocols'").fetchone() is None
    assert not lab.c.in_transaction
    assert upgrade(lab.c)==5


def test_damaged_v4_denied_without_migration(lab):
    lab.c.execute("DROP TRIGGER immutable_prediction_receipts_update")
    with pytest.raises(ValueError):
        upgrade(lab.c)
    assert lab.c.execute("PRAGMA user_version").fetchone()[0]==4


@pytest.mark.parametrize("change",[
    {"fit_end":"2025-03-02"},{"calibration_end":"2025-03-01"},
    {"fit_start":"2025-1-01"},{"training_cutoff":"2025-03-15T12:00:00Z"},
    {"evaluation_start":CUTOFF},{"evaluation_end":"2025-05-02T00:00:00Z"},
    {"registered_at":"2025-05-02T00:00:00Z"},{"min_fit":True},
    {"min_calibration":1},{"min_matched":0},{"protocol_id":"REAL-protocol"},
    {"evaluation_cohort_id":"REAL-cohort"},{"training_cutoff":"2025-05-01T12:00:00"},
])
def test_invalid_protocol_fails_closed(lab,change):
    upgrade(lab.c)
    with pytest.raises(ValueError):
        proto_api().register_protocol(lab.c,protocol(**change))
    assert registry_counts(lab.c)==(0,0,0,1)


def test_protocol_immutable_exact_replay(lab):
    upgrade(lab.c)
    p=proto_api().register_protocol(lab.c,protocol())
    assert proto_api().register_protocol(lab.c,protocol(registered_at="2025-04-30T19:00:00+07:00"))==p
    with pytest.raises(ValueError):
        proto_api().register_protocol(lab.c,protocol(min_fit=5))
    with pytest.raises(sqlite3.IntegrityError):
        lab.c.execute("DELETE FROM training_protocols")
    assert registry_counts(lab.c)==(1,0,0,1)


def test_dataset_exact_chronology_lineage_and_orientation(prepared):
    ds=dataset(prepared)
    assert tuple(x.match_id for x in ds.fit)==tuple(f"SYN-m-fit{j}" for j in range(4))
    assert tuple(x.match_id for x in ds.calibration)==tuple(f"SYN-m-cal{j}" for j in range(4))
    assert tuple(x.outcome_a for x in ds.fit)==(1,0,1,0)
    assert tuple(x.outcome_a for x in ds.calibration)==(1,0,1,0)
    assert not ({x.event_id for x in ds.fit}&{x.event_id for x in ds.calibration})
    for x in (*ds.fit,*ds.calibration):
        assert x.result_id not in x.history_result_ids
        assert tuple(n for n,_ in x.values)==FEATURE_NAMES
        old=commitment.get_commitment(prepared.c,x.prediction_id)
        assert old.prediction.commitment_digest==x.commitment_digest
        assert tuple(map(tuple,json.loads(old.receipt_json)["features"]["values"]))==x.values
    assert dataset(prepared)==ds
    assert not prepared.c.in_transaction


def test_future_result_correction_cannot_leak_into_dataset(prepared):
    before=dataset(prepared)
    prepared.result("cal0",revision=2,outcome=0,observed="2025-05-04T10:00:00Z",
                    available="2025-05-04T11:00:00Z")
    assert dataset(prepared)==before


def test_latest_unavailable_correction_blocks_old_label(prepared):
    prepared.result("cal0",revision=2,outcome=0,observed="2025-04-20T10:00:00Z",available=None)
    ds=dataset(prepared)
    assert len(ds.fit)==4 and len(ds.calibration)==3
    assert "SYN-m-cal0" not in {x.match_id for x in ds.calibration}
    with pytest.raises(ValueError):
        train(prepared)
    assert registry_counts(prepared.c)==(1,0,0,1) and list(prepared.root.iterdir())==[]


def test_fit_label_received_after_calibration_starts_is_excluded(prepared):
    key="fit0"
    p=prepared.commit(key)
    prepared.result(key,revision=2,outcome=0,observed="2025-03-02T10:00:00Z",
                    available="2025-03-02T11:00:00Z")
    assert prepared.evaluate(p,key,"2025-03-02T12:00:00Z").status=="RECORDED"
    ds=dataset(prepared)
    assert len(ds.fit)==3 and "SYN-m-fit0" not in {x.match_id for x in ds.fit}
    with pytest.raises(ValueError):
        train(prepared)


def test_label_without_visible_assessment_not_used(prepared):
    prepared.fixture("late-assess","2025-03-09")
    p=prepared.commit("late-assess")
    prepared.result("late-assess",outcome=1)
    prepared.evaluate(p,"late-assess","2025-05-04T12:00:00Z")
    assert len(dataset(prepared).calibration)==4


def test_same_event_cannot_cross_splits(lab):
    upgrade(lab.c)
    # An earlier corrected event date preserves valid actual-start chronology
    # but contradicts the earlier frozen calibration event metadata.
    lab.example("one","2025-03-01",1,tournament="SYN-same-event")
    lab.example("two","2025-03-03",0,tournament="SYN-same-event",revision=2,event_day="2025-01-01")
    proto_api().register_protocol(lab.c,protocol())
    with pytest.raises(ValueError):
        dataset(lab)
    assert registry_counts(lab.c)==(1,0,0,1)


def test_insufficient_or_single_class_data_not_fitted(lab):
    upgrade(lab.c)
    seed(lab,cal_labels=(1,1,1,1))
    proto_api().register_protocol(lab.c,protocol())
    with pytest.raises(ValueError):
        train(lab)
    assert registry_counts(lab.c)==(1,0,0,1)
    assert list(lab.root.iterdir())==[]


def test_fit_scaler_only_fit_rows_and_repeatability(prepared):
    from atp_lab.training.fit import fit_logistic
    ds=dataset(prepared)
    first,second=fit_logistic(ds),fit_logistic(ds)
    for attr in ("mean","scale","coef"):
        assert getattr(first,attr)==pytest.approx(getattr(second,attr),abs=1e-12)
    for attr in ("intercept","platt_slope","platt_intercept"):
        assert getattr(first,attr)==pytest.approx(getattr(second,attr),abs=1e-12)
    fit_mean=[sum(dict(x.values)[name] for x in ds.fit)/4 for name in FEATURE_NAMES[10:]]
    cal_mean=[sum(dict(x.values)[name] for x in ds.calibration)/4 for name in FEATURE_NAMES[10:]]
    assert first.mean[:10]==pytest.approx([0.]*10,abs=1e-12)
    assert first.mean[10:]==pytest.approx(fit_mean,abs=1e-12)
    assert any(abs(a-b)>1e-6 for a,b in zip(fit_mean,cal_mean))
    assert all(s>0 and math.isfinite(s) for s in first.scale)


def test_frozen_artifact_hash_prediction_symmetry_and_restart(trained):
    lab,r=trained
    path=lab.root/r.artifact_name
    raw=path.read_bytes()
    assert sha256(raw).hexdigest()==r.model_digest
    data=json.loads(raw)
    assert data["feature_names"]==list(FEATURE_NAMES)
    assert data["dataset_digest"]==r.dataset_digest
    assert data["protocol_digest"]==r.protocol_digest
    assert data["dependency_digest"] and data["code_digest"] and data["config_digest"]==r.config_digest
    assert r.fit_n==r.calibration_n==4
    frozen=api().load_verified_candidate(lab.c,r.model_id,model_dir=lab.root)
    v=dataset(lab).fit[0].values
    swapped=tuple((n,-x if j<10 else x) for j,(n,x) in enumerate(v))
    prob=frozen.predict(v)
    assert 1e-12<=prob<=1-1e-12
    assert prob+frozen.predict(swapped)==pytest.approx(1.,abs=1e-12)
    zero=tuple((n,0 if j<10 else x) for j,(n,x) in enumerate(v))
    assert frozen.predict(zero)==pytest.approx(.5,abs=1e-12)
    for wrong in (v[::-1],v[:-1],((v[0][0],float("nan")),*v[1:]),
                  ((v[0][0],True),*v[1:])):
        with pytest.raises(ValueError):
            frozen.predict(wrong)
    with closing(open_writer(lab.path)) as restarted:
        assert api().load_verified_candidate(restarted,r.model_id,model_dir=lab.root).predict(v)==prob
        assert api().train_candidate(restarted,"SYN-protocol",created_at=FROZEN,model_dir=lab.root)==r
    assert path.read_bytes()==raw
    assert registry_counts(lab.c)==(1,1,0,2)
    assert api().active_model_id(lab.c)==BASE


@pytest.mark.parametrize("created",[CUTOFF,"2025-04-30T12:00:00Z","2025-05-04T12:00:00Z"])
def test_freeze_clock_invalid_no_artifact(prepared,created):
    with pytest.raises(ValueError):
        train(prepared,created_at=created)
    assert registry_counts(prepared.c)==(1,0,0,1)
    assert list(prepared.root.iterdir())==[]


def test_unsafe_artifact_directory_rejected(prepared,tmp_path):
    bad=tmp_path/"other"
    bad.mkdir()
    for root in (bad,prepared.root/".."/"model_artifacts","model_artifacts"):
        with pytest.raises((ValueError,OSError)):
            train(prepared,model_dir=root)
    symlink=tmp_path/"linked"
    symlink.mkdir()
    try:
        (symlink/"model_artifacts").symlink_to(prepared.root,target_is_directory=True)
    except OSError:
        pass # Windows may disallow symlink creation; traversal check still exercised.
    else:
        with pytest.raises((ValueError,OSError)):
            train(prepared,model_dir=symlink/"model_artifacts")
    assert registry_counts(prepared.c)==(1,0,0,1)
    assert list(prepared.root.iterdir())==[]


def test_corrupt_or_oversize_artifact_never_infers(trained):
    lab,r=trained
    path=lab.root/r.artifact_name
    raw=path.read_bytes()
    lab.fixture("future","2025-05-10")
    baseline=lab.commit("future")
    for bad in (b"not json",b" "*(9*1024*1024)):
        path.write_bytes(bad)
        with pytest.raises((ValueError,OSError)):
            api().load_verified_candidate(lab.c,r.model_id,model_dir=lab.root)
        with pytest.raises((ValueError,OSError)):
            lab.commit("future",r.model_id)
        with pytest.raises((ValueError,OSError)):
            train(lab)
        assert lab.c.execute("SELECT count(*) FROM predictions WHERE model_id=?",(r.model_id,)).fetchone()[0]==0
    path.write_bytes(raw)
    p=lab.commit("future",r.model_id)
    assert commitment.get_commitment(lab.c,baseline.prediction.prediction_id)==baseline
    assert p.prediction.model_id==r.model_id


def test_failed_db_registration_has_no_partial_model_and_safe_orphan_retry(prepared):
    def authorize(action,arg1,arg2,db,trigger):
        if action==sqlite3.SQLITE_INSERT and arg1=="candidate_artifacts":
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
    prepared.c.set_authorizer(authorize)
    try:
        with pytest.raises(sqlite3.DatabaseError):
            train(prepared)
    finally:
        prepared.c.set_authorizer(None)
    assert registry_counts(prepared.c)==(1,0,0,1)
    assert not prepared.c.in_transaction
    orphans=list(prepared.root.iterdir())
    assert len(orphans)==1
    raw=orphans[0].read_bytes()
    r=train(prepared)
    assert prepared.root/r.artifact_name==orphans[0] and orphans[0].read_bytes()==raw
    assert registry_counts(prepared.c)==(1,1,0,2)


def test_candidate_artifacts_and_protocol_cannot_be_mutated(trained):
    lab,r=trained
    with pytest.raises(sqlite3.IntegrityError):
        lab.c.execute("DELETE FROM candidate_artifacts")
    with pytest.raises(sqlite3.IntegrityError):
        lab.c.execute("UPDATE training_protocols SET digest='bad'")
    assert api().load_verified_candidate(lab.c,r.model_id,model_dir=lab.root).receipt==r


def future_cycle(lab,r,*,mismatch_cutoff=False,missing_last=True):
    for j in range(3):
        lab.fixture(f"future{j}","2025-05-10",pair=("SYN-A","SYN-C"))
    fixtures=tuple(lab.rows[f"future{j}"][0] for j in range(3))
    service.register_cohort(lab.c,"SYN-future-cohort",fixtures,(BASE,r.model_id),
                            registered_at="2025-05-09T09:00:00Z",cutoff_end=EVAL_END)
    commitments=[]
    for j in range(2 if missing_last else 3):
        key=f"future{j}"
        b=lab.commit(key)
        a=lab.commit(key,r.model_id,clock="2025-05-09T12:01:00Z" if mismatch_cutoff and j==0 else None)
        lab.result(key,outcome=j%2)
        assert lab.evaluate(b,key).status=="RECORDED"
        assert lab.evaluate(a,key).status=="RECORDED"
        commitments.append((b,a))
    return commitments


def test_candidate_preview_and_commit_preserve_baseline_and_freeze(trained):
    lab,r=trained
    lab.fixture("future","2025-05-10")
    b=lab.commit("future")
    with pytest.raises(ValueError):
        commitment.commit_prediction(lab.c,lab.rows["future"][0],tuple(lab.events),
              cutoff="2025-05-09T12:00:00Z",created_at="2025-05-09T12:00:00Z",model_id=r.model_id)
    p=lab.commit("future",r.model_id)
    assert b.feature==p.feature and b.prediction.model_id==BASE
    preview=inference.predict_fixture(lab.c,lab.rows["future"][0],tuple(lab.events),
            cutoff="2025-05-09T12:00:00Z",model_id=r.model_id,model_dir=lab.root)
    assert preview.probability_a==p.prediction.probability_a
    assert p.prediction.commitment_digest!=b.prediction.commitment_digest
    lab.result("future")
    assert lab.evaluate(p,"future").status=="RECORDED"
    assert lab.commit("future",r.model_id)==p
    # Frozen DB evidence remains verifiable even if local artifact is lost.
    (lab.root/r.artifact_name).unlink()
    assert commitment.get_commitment(lab.c,p.prediction.prediction_id)==p
    assert commitment.get_commitment(lab.c,b.prediction.prediction_id)==b


def test_candidate_cannot_predict_consumed_training_fixture(trained):
    lab,r=trained
    with pytest.raises(ValueError):
        lab.commit("fit0",r.model_id)
    assert lab.c.execute("SELECT count(*) FROM predictions WHERE model_id=?",(r.model_id,)).fetchone()[0]==0


def test_future_matched_comparison_has_fixed_coverage_and_no_auto_promotion(trained):
    lab,r=trained
    old=future_cycle(lab,r)
    comp=api().candidate_comparison(lab.c,r.model_id,as_of=REPORT)
    assert comp["status"]=="SUFFICIENT_SYNTHETIC" and comp["matched_n"]==2
    assert tuple(comp["matched_keys"])==("SYN-f-future0","SYN-f-future1")
    assert comp["target_n"]==3
    assert comp["models"][BASE]["scored_n"]==comp["models"][r.model_id]["scored_n"]==2
    assert comp["models"][r.model_id]["scored_coverage"]==pytest.approx(2/3)
    assert comp["ll_delta"]==pytest.approx(comp["matched_metrics"][r.model_id]["log_loss"]-
                                           comp["matched_metrics"][BASE]["log_loss"])
    assert comp["uncertainty"]=="DESCRIPTIVE_ONLY"
    assert api().active_model_id(lab.c)==BASE
    assert api().candidate_comparison(lab.c,r.model_id,as_of=REPORT)==comp
    lab.result("future0",revision=2,outcome=1,observed="2025-06-02T10:00:00Z",available=None)
    latest=api().candidate_comparison(lab.c,r.model_id,as_of=APPROVAL)
    assert latest["matched_n"]==1 and latest["status"]=="INSUFFICIENT_MATCHED_SUPPORT"
    assert api().candidate_comparison(lab.c,r.model_id,as_of=REPORT)==comp
    assert commitment.get_commitment(lab.c,old[0][1].prediction.prediction_id)==old[0][1]


def test_comparison_excludes_different_information_cutoff(trained):
    lab,r=trained
    future_cycle(lab,r,mismatch_cutoff=True)
    comp=api().candidate_comparison(lab.c,r.model_id,as_of=REPORT)
    assert comp["matched_n"]==1 and comp["status"]=="INSUFFICIENT_MATCHED_SUPPORT"
    assert comp["unmatched_reasons"]["DIFFERENT_INFORMATION_SET"]==1
    assert comp["target_n"]==3


def approval(lab,r,comp,**changes):
    args=dict(approval_id="SYN-owner-promote",action="PROMOTE",from_model_id=BASE,
              to_model_id=r.model_id,model_digest=r.model_digest,config_digest=r.config_digest,
              evidence_digest=comp["digest"],decided_at=REPORT,approved=True)
    args.update(changes)
    return api().OwnerApproval(**args)


def test_promotion_requires_exact_manual_approval_and_support(trained):
    lab,r=trained
    future_cycle(lab,r)
    comp=api().candidate_comparison(lab.c,r.model_id,as_of=REPORT)
    for bad in (None,approval(lab,r,comp,approved=False),
                approval(lab,r,comp,evidence_digest="0"*64),
                approval(lab,r,comp,model_digest="0"*64),
                approval(lab,r,comp,config_digest="0"*64),
                approval(lab,r,comp,from_model_id=r.model_id),
                approval(lab,r,comp,decided_at="2025-05-11T12:00:00Z")):
        with pytest.raises(ValueError):
            api().promote_candidate(lab.c,r.model_id,bad,model_dir=lab.root)
    assert registry_counts(lab.c)==(1,1,0,2)
    assert api().active_model_id(lab.c)==BASE


def test_promotion_denies_insufficient_matched_support(trained):
    lab,r=trained
    future_cycle(lab,r,mismatch_cutoff=True)
    comp=api().candidate_comparison(lab.c,r.model_id,as_of=REPORT)
    with pytest.raises(ValueError):
        api().promote_candidate(lab.c,r.model_id,approval(lab,r,comp),model_dir=lab.root)
    assert api().active_model_id(lab.c)==BASE


def test_promotion_rollback_restart_and_db_backup_preserve_forecasts(trained,tmp_path):
    from atp_lab.database.backup import backup_database,restore_database
    lab,r=trained
    old=future_cycle(lab,r)
    comp=api().candidate_comparison(lab.c,r.model_id,as_of=REPORT)
    consent=approval(lab,r,comp)
    promote=api().promote_candidate(lab.c,r.model_id,consent,model_dir=lab.root)
    assert api().active_model_id(lab.c)==r.model_id
    assert api().promote_candidate(lab.c,r.model_id,consent,model_dir=lab.root)==promote
    assert promote.from_model_id==BASE and promote.to_model_id==r.model_id
    bm=inference.synthetic_model_version(created_at="2024-01-01T00:00:00Z")
    roll=api().OwnerApproval("SYN-owner-rollback","ROLLBACK",r.model_id,BASE,
             bm.model_digest,bm.config_digest,promote.digest,ROLLBACK,True)
    with pytest.raises(ValueError):
        api().rollback_promotion(lab.c,replace(roll,evidence_digest="0"*64),model_dir=lab.root)
    back=api().rollback_promotion(lab.c,roll,model_dir=lab.root)
    assert api().active_model_id(lab.c)==BASE and back.to_model_id==BASE
    assert api().rollback_promotion(lab.c,roll,model_dir=lab.root)==back
    assert registry_counts(lab.c)==(1,1,2,2)
    with pytest.raises(sqlite3.IntegrityError):
        lab.c.execute("DELETE FROM model_lifecycle_events")
    for b,a in old:
        assert commitment.get_commitment(lab.c,b.prediction.prediction_id)==b
        assert commitment.get_commitment(lab.c,a.prediction.prediction_id)==a
    with closing(open_writer(lab.path)) as restarted:
        assert api().active_model_id(restarted)==BASE
    dest=restore_database(backup_database(lab.path,tmp_path/"trained-backup.sqlite"),tmp_path/"trained-restored.sqlite")
    with closing(open_reader(dest)) as reader:
        assert api().active_model_id(reader)==BASE
        assert api().load_verified_candidate(reader,r.model_id,model_dir=lab.root).receipt==r
        assert api().candidate_comparison(reader,r.model_id,as_of=REPORT)==comp
        assert not reader.in_transaction


@pytest.mark.parametrize("n,as_of,eligible",[
    (199,"2025-05-08T12:00:00Z",False),(200,"2025-05-08T11:59:59Z",False),
    (200,"2025-05-08T12:00:00Z",True),(201,"2025-05-09T12:00:00Z",True),
])
def test_operational_weekly_flag_not_a_training_or_power_claim(n,as_of,eligible):
    r=api().readiness_flag(n,last_check_at=CUTOFF,as_of=as_of)
    assert r["eligible_to_request"] is eligible
    assert r["new_eligible_n"]==n and r["manual_only"] is True
    assert r["statistical_power_claim"] is False


def test_readiness_counts_distinct_new_mature_matches(prepared):
    r=api().training_readiness(prepared.c,last_check_at="2025-01-01T00:00:00Z",as_of=CUTOFF)
    assert r["new_eligible_n"]==8 and not r["eligible_to_request"]
    assert registry_counts(prepared.c)==(1,0,0,1)
