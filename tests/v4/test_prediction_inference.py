"""S4.3: read-only SQLite assembly and deterministic synthetic inference."""
from contextlib import closing
from dataclasses import replace
from datetime import date
from hashlib import sha256

import pytest

from atp_lab.database import identity as i, forecast as f
from atp_lab.database.connection import open_reader, open_writer
from atp_lab.database.migrations import migrate

CUTOFF = "2025-06-29T12:00:00Z"
EARLY = "2025-05-01T12:00:00Z"
OBS = "2025-06-28T12:00:00Z"
READY = "2025-06-28T13:00:00Z"
START = "2025-06-30T14:00:00Z"
HOBS = "2025-06-03T12:00:00Z"
HREADY = "2025-06-03T13:00:00Z"
D = sha256(b"synthetic").hexdigest()


def api():
    from atp_lab.prediction import inference
    return inference


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "prediction.sqlite"
    with closing(open_writer(path)) as c:
        migrate(c)
        i.migrate_identity(c)
        f.migrate_forecast(c)
        c.execute("BEGIN IMMEDIATE")
        for source in ("SYN-feed","SYN-other"):
            i.put_source(c,i.Source(source,"SYNTHETIC","LOCKED"))
        for player in ("SYN-A","SYN-B","SYN-C"):
            i.put_player(c,i.Player(player))
        for event in ("SYN-event","SYN-old-event"):
            i.put_tournament(c,i.Tournament(event,event,"2025","ATP250","HARD"))
        i.put_match(c,i.Match("SYN-m","SYN-event","SYN-A","SYN-B"))
        i.put_match(c,i.Match("SYN-h","SYN-old-event","SYN-A","SYN-C"))
        i.put_snapshot(c,i.Snapshot("SYN-fsnap","SYN-feed",D,OBS))
        i.put_snapshot(c,i.Snapshot("SYN-hsnap","SYN-feed",D,HOBS))
        i.append_fixture(c,i.Fixture("SYN-f","SYN-m",1,"SYN-feed","SYN-fsnap",
                                    "SYN-A","SYN-B",OBS,READY,START,"SCHEDULED"))
        i.append_result(c,i.Result("SYN-r","SYN-h",1,"SYN-feed","SYN-hsnap",
                                  HOBS,HREADY,"2025-06-02T16:00:00Z",
                                  "2025-06-02T14:00:00Z","COMPLETED","SYN-A"))
        c.commit()
        yield c,path


def metadata():
    a = api()
    return (
        a.EventMetadata("SYN-event",1,date(2025,6,30),EARLY,EARLY),
        a.EventMetadata("SYN-old-event",1,date(2025,6,1),EARLY,EARLY),
    )


def register(c, **change):
    a = api()
    version = replace(a.synthetic_model_version(created_at=EARLY), **change)
    c.execute("BEGIN IMMEDIATE")
    f.append_model(c,version)
    c.commit()
    return version


def predict(c, *, fixture="SYN-f", events=None, cutoff=CUTOFF):
    return api().predict_fixture(c,fixture,events if events is not None else metadata(),
                                 cutoff=cutoff)


def add_fixture(c, *, revision=2, source="SYN-feed", observed=OBS,
                available=READY,state="SCHEDULED",scheduled=START):
    c.execute("BEGIN IMMEDIATE")
    i.put_snapshot(c,i.Snapshot("SYN-snap2",source,D,observed))
    i.append_fixture(c,i.Fixture("SYN-f2","SYN-m",revision,source,"SYN-snap2",
                                "SYN-A","SYN-B",observed,available,scheduled,state))
    c.commit()


def test_readonly_inference_bound_to_features_model_and_cutoff(db):
    c,path = db
    version = register(c)
    with closing(open_reader(path)) as reader:
        out = predict(reader)
        assert out == predict(reader,cutoff="2025-06-29T19:00:00+07:00")
        assert out.fixture_id == "SYN-f" and out.match_id == "SYN-m"
        assert out.model == version
        assert out.features.result_ids == ("SYN-r",)
        assert out.features.cutoff == "2025-06-29T12:00:00.000000Z"
        assert len(out.features.values) == 18
        assert .5 < out.probability_a < 1
        assert len(out.digest) == 64
        assert not reader.in_transaction
    for table in ("feature_snapshots","predictions","evaluations","job_runs"):
        assert c.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0


def test_missing_model_rejected(db):
    c,_ = db
    a = api()
    with pytest.raises(a.InferenceError):
        predict(c)


@pytest.mark.parametrize("field", ["model_digest","config_digest"])
def test_wrong_model_digest_rejected(db,field):
    c,_ = db
    a = api()
    register(c,**{field:"0"*64})
    with pytest.raises(a.InferenceError):
        predict(c)


def test_future_model_rejected(db):
    c,_ = db
    a = api()
    version = a.synthetic_model_version(created_at="2025-06-29T13:00:00Z")
    c.execute("BEGIN IMMEDIATE")
    f.append_model(c,version)
    c.commit()
    with pytest.raises(a.InferenceError):
        predict(c)


@pytest.mark.parametrize("change", [
    {}, {"state":"CANCELLED","scheduled":None},
    {"available":None}, {"source":"SYN-other","revision":1},
])
def test_stale_or_ambiguous_fixture_rejected(db,change):
    c,_ = db
    a = api()
    register(c)
    add_fixture(c,**change)
    with pytest.raises(a.InferenceError):
        predict(c)


def test_future_fixture_revision_does_not_change_asof_prediction(db):
    c,_ = db
    register(c)
    first = predict(c)
    add_fixture(c,observed="2025-06-29T13:00:00Z",
                available="2025-06-29T14:00:00Z")
    assert predict(c) == first


def test_new_visible_fixture_can_be_used(db):
    c,_ = db
    register(c)
    add_fixture(c)
    assert predict(c,fixture="SYN-f2").fixture_id == "SYN-f2"


def test_observed_target_result_blocks_prediction(db):
    c,_ = db
    a = api()
    register(c)
    c.execute("BEGIN IMMEDIATE")
    i.append_result(c,i.Result("SYN-target-r","SYN-m",1,"SYN-feed",
        "SYN-fsnap",OBS,READY,None,None,"UNKNOWN",None))
    c.commit()
    with pytest.raises(a.InferenceError):
        predict(c)


@pytest.mark.parametrize("cutoff", [START,"2025-06-30T14:00:01Z"])
def test_at_or_after_scheduled_start_rejected(db,cutoff):
    c,_ = db
    a = api()
    register(c)
    with pytest.raises(a.InferenceError):
        predict(c,cutoff=cutoff)


def test_missing_target_metadata_rejected(db):
    c,_ = db
    a = api()
    register(c)
    with pytest.raises(a.InferenceError):
        predict(c,events=metadata()[1:])


def test_unknown_latest_metadata_availability_blocks_target(db):
    c,_ = db
    a = api()
    register(c)
    events = metadata()
    correction = replace(events[0],revision=2,observed_at=OBS,available_at=None)
    with pytest.raises(a.InferenceError):
        predict(c,events=(*events,correction))


def test_future_event_metadata_does_not_change_digest(db):
    c,_ = db
    register(c)
    events = metadata()
    first = predict(c,events=events)
    correction = replace(events[0],revision=2,event_start=date(2025,6,29),
                         observed_at="2025-06-29T13:00:00Z",
                         available_at="2025-06-29T14:00:00Z")
    assert predict(c,events=(*events,correction)) == first


def test_metadata_revision_is_bound_even_if_same_event_date(db):
    c,_ = db
    register(c)
    events = metadata()
    first = predict(c,events=events)
    correction = replace(events[0],revision=2,observed_at=OBS,available_at=READY)
    second = predict(c,events=(*events,correction))
    assert first.features == second.features
    assert first.digest != second.digest


def test_caller_transaction_preserved(db):
    c,_ = db
    a = api()
    register(c)
    c.execute("BEGIN")
    with pytest.raises(a.InferenceError):
        predict(c)
    assert c.in_transaction
    c.rollback()


def test_damaged_schema_rejected(db):
    c,_ = db
    register(c)
    c.execute("DROP TRIGGER immutable_predictions_update")
    with pytest.raises(ValueError):
        predict(c)
