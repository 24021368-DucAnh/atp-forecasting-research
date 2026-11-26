"""S3.3: rights-first transactional synthetic ingestion and failure receipts."""
from contextlib import closing
from dataclasses import replace
import json
import sqlite3

import pytest

from atp_lab.database import identity as i, forecast as f
from atp_lab.database.connection import open_writer
from atp_lab.database.migrations import migrate
from atp_lab.ingestion import adapter

STARTED = "2026-01-02T13:00:00Z"
OBS = "2026-01-02T13:01:00Z"
READY = "2026-01-02T13:02:00Z"
END = "2026-01-02T13:03:00Z"
MATCH_START = "2026-01-02T10:00:00Z"
PUBLISHED = "2026-01-02T12:00:00Z"


def api():
    from atp_lab.ingestion import pipeline
    return pipeline


class Fake:
    def __init__(self,*responses):
        self.responses = list(responses)
        self.calls = []

    def fetch(self,url):
        self.calls.append(url)
        response = self.responses.pop(0)
        if isinstance(response,Exception):
            raise response
        return response


@pytest.fixture
def db(tmp_path):
    path = tmp_path/"ingest.sqlite"
    with closing(open_writer(path)) as c:
        migrate(c)
        i.migrate_identity(c)
        f.migrate_forecast(c)
        c.execute("BEGIN IMMEDIATE")
        i.put_source(c,i.Source("SYN-feed","SYNTHETIC","LOCKED"))
        for alias,player in (("a","SYN-A"),("b","SYN-B")):
            i.put_player(c,i.Player(player))
            i.put_alias(c,i.PlayerAlias("SYN-feed",alias,player))
        i.put_tournament(c,i.Tournament("SYN-t","SYN-event","2026","ATP250","HARD"))
        i.put_match(c,i.Match("SYN-m","SYN-t","SYN-A","SYN-B"))
        i.put_match_alias(c,i.MatchAlias("SYN-feed","m","SYN-m"))
        c.commit()
        yield c,path


def fixture(**change):
    return dict({"match_id":"m","player_1":"b","player_2":"a","revision":1,
                 "scheduled_start":MATCH_START,"state":"SCHEDULED"}, **change)


def result(**change):
    return dict({"match_id":"m","player_1":"b","player_2":"a","revision":1,
                 "published_at":PUBLISHED,"actual_start":MATCH_START,
                 "state":"COMPLETED","winner":"a"}, **change)


def payload(rows,kind="fixtures"):
    return json.dumps({kind:rows}).encode("utf-8")


def run(c,transport,**change):
    defaults = dict(job_id="SYN-job1",started_at=STARTED,observed_at=OBS,
                    available_at=READY,ended_at=END,sleep=lambda _: None)
    policy = change.pop("policy",adapter.SourcePolicy("SYN-feed",enabled=True))
    url = change.pop("url",adapter.FIXTURES_ENDPOINT)
    defaults.update(change)
    return api().ingest_batch(c,policy,url,transport,**defaults)


def counts(c):
    return tuple(c.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                 for table in ("source_snapshots","fixture_versions","result_versions",
                               "job_runs","data_quality_issues"))


def test_success_persists_snapshot_rows_and_terminal_receipt(db):
    c,_ = db
    transport = Fake(payload([fixture()]))
    report = run(c,transport)
    assert report.status == "SUCCEEDED" and report.reason is None
    assert (report.inserted,report.replayed) == (1,0)
    assert counts(c) == (1,1,0,1,0)
    assert c.execute("SELECT snapshot_id FROM fixture_versions").fetchone()[0] == report.snapshot_id
    assert c.execute("SELECT kind,status,attempt FROM job_runs").fetchall() == [("INGEST","SUCCEEDED",1)]
    assert not c.in_transaction


def test_result_correction_keeps_first_revision(db):
    c,_ = db
    run(c,Fake(payload([fixture()])))
    run(c,Fake(payload([result()],"results")),url=adapter.RESULTS_ENDPOINT,
        job_id="SYN-job2")
    report = run(c,Fake(payload([result(revision=2,winner="b")],"results")),
                 url=adapter.RESULTS_ENDPOINT,job_id="SYN-job3")
    assert report.inserted == 1
    assert c.execute("SELECT revision,winner FROM result_versions ORDER BY revision").fetchall() == [
        (1,"SYN-A"),(2,"SYN-B")]
    assert counts(c) == (3,1,2,3,0)


def test_exact_replay_with_new_job_is_noop_for_data(db):
    c,_ = db
    raw = payload([fixture()])
    first = run(c,Fake(raw))
    again = run(c,Fake(raw),job_id="SYN-job2")
    assert again.status == "SUCCEEDED"
    assert (again.inserted,again.replayed) == (0,1)
    assert first.snapshot_id == again.snapshot_id
    assert counts(c) == (1,1,0,2,0)


def test_later_reobservation_preserves_first_lineage(db):
    c,_ = db
    raw = payload([fixture()])
    first = run(c,Fake(raw))
    before = c.execute("SELECT * FROM fixture_versions").fetchall()
    again = run(c,Fake(raw),job_id="SYN-job2",
                observed_at="2026-01-02T13:04:00Z",
                available_at="2026-01-02T13:05:00Z",
                ended_at="2026-01-02T13:06:00Z")
    assert again.status == "SUCCEEDED"
    assert (again.inserted,again.replayed) == (0,1)
    assert again.snapshot_id != first.snapshot_id
    assert c.execute("SELECT * FROM fixture_versions").fetchall() == before
    assert counts(c) == (2,1,0,2,0)


def test_later_reobservation_after_restart(db):
    c,path = db
    raw = payload([fixture()])
    run(c,Fake(raw))
    with closing(open_writer(path)) as restarted:
        report = run(restarted,Fake(raw),job_id="SYN-job2",
                     observed_at="2026-01-02T13:04:00Z",available_at=None,
                     ended_at="2026-01-02T13:06:00Z")
        assert report.status == "SUCCEEDED" and report.replayed == 1
    assert counts(c) == (2,1,0,2,0)


@pytest.mark.parametrize("change", [
    {"scheduled_start":"2026-01-02T11:00:00Z"},{"state":"POSTPONED"},
])
def test_conflicting_revision_rolls_back_entire_batch(db,change):
    c,_ = db
    run(c,Fake(payload([fixture()])))
    original = c.execute("SELECT * FROM fixture_versions").fetchall()
    report = run(c,Fake(payload([fixture(revision=2),fixture(**change)])),
                 job_id="SYN-job2",observed_at="2026-01-02T13:04:00Z",
                 available_at=None,ended_at="2026-01-02T13:06:00Z")
    assert report.status == "FAILED" and report.reason == "REVISION_CONFLICT"
    assert report.snapshot_id is None
    assert (report.inserted,report.replayed) == (0,0)
    assert counts(c) == (1,1,0,2,1)
    assert c.execute("SELECT * FROM fixture_versions").fetchall() == original
    assert c.execute("SELECT reason FROM data_quality_issues").fetchall() == [("REVISION_CONFLICT",)]
    assert not c.in_transaction


def test_earlier_observation_cannot_backdate(db):
    c,_ = db
    raw = payload([fixture()])
    run(c,Fake(raw))
    report = run(c,Fake(raw),job_id="SYN-job2",observed_at=STARTED)
    assert report.status == "FAILED" and report.reason == "REVISION_CONFLICT"
    assert counts(c) == (1,1,0,2,1)


def test_same_observation_different_availability_conflicts(db):
    c,_ = db
    raw = payload([fixture()])
    run(c,Fake(raw))
    report = run(c,Fake(raw),job_id="SYN-job2",available_at=None)
    assert report.status == "FAILED" and report.reason == "REVISION_CONFLICT"
    assert counts(c) == (1,1,0,2,1)


def test_invalid_batch_quarantined_without_raw_payload(db):
    c,_ = db
    secret = "DO-NOT-LOG-PAYLOAD"
    report = run(c,Fake(payload([fixture(),fixture(match_id=secret)])))
    assert report.status == "FAILED" and report.reason == "PARSE_REJECTED"
    assert report.snapshot_id is None
    assert counts(c) == (0,0,0,1,1)
    assert c.execute("SELECT reason FROM data_quality_issues").fetchall() == [("PARSE_REJECTED",)]
    assert secret not in repr(report)
    assert secret not in repr(c.execute("SELECT * FROM data_quality_issues").fetchall())


@pytest.mark.parametrize("policy,url", [
    (adapter.SourcePolicy("SYN-feed"),adapter.FIXTURES_ENDPOINT),
    (adapter.SourcePolicy("SYN-feed",enabled=True),"https://example.com/"),
    (adapter.SourcePolicy("SYN-missing",enabled=True),adapter.FIXTURES_ENDPOINT),
    (adapter.SourcePolicy("REAL",enabled=True),adapter.FIXTURES_ENDPOINT),
])
def test_blocked_scope_never_fetches(db,policy,url):
    c,_ = db
    transport = Fake(payload([fixture()]))
    delays = []
    report = run(c,transport,policy=policy,url=url,sleep=delays.append)
    assert report.status == "BLOCKED" and report.reason == "FETCH_BLOCKED"
    assert transport.calls == delays == []
    assert counts(c) == (0,0,0,1,0)


def test_retry_then_success(db):
    c,_ = db
    transport = Fake(adapter.TransientFetchError("temporary"),payload([fixture()]))
    delays = []
    report = run(c,transport,sleep=delays.append)
    assert report.status == "SUCCEEDED" and report.inserted == 1
    assert len(transport.calls) == 2 and delays == [.25]
    assert counts(c) == (1,1,0,1,0)


@pytest.mark.parametrize("failure,reason", [
    (adapter.TransientFetchError("secret"),"FETCH_TRANSIENT_EXHAUSTED"),
    (adapter.PermanentFetchError("secret"),"FETCH_PERMANENT"),
    (b"","INVALID_PAYLOAD"),
])
def test_fetch_failure_sanitized_terminal_receipt(db,failure,reason):
    c,_ = db
    report = run(c,Fake(failure,failure,failure))
    assert report.status == "FAILED" and report.reason == reason
    assert counts(c) == (0,0,0,1,1)
    assert c.execute("SELECT reason FROM data_quality_issues").fetchall() == [(reason,)]
    assert "secret" not in repr(report)


def test_completed_job_id_cannot_execute_again(db):
    c,_ = db
    run(c,Fake(payload([])))
    transport = Fake(payload([fixture()]))
    with pytest.raises(ValueError):
        run(c,transport)
    assert transport.calls == []
    assert counts(c) == (1,0,0,1,0)


@pytest.mark.parametrize("change", [
    {"job_id":"REAL-job"},{"started_at":END},{"ended_at":STARTED},
    {"available_at":"2026-01-02T13:04:00Z"},{"observed_at":"2026-01-02T13:01:00"},
])
def test_invalid_invocation_no_fetch_or_write(db,change):
    c,_ = db
    transport = Fake(payload([]))
    with pytest.raises(ValueError):
        run(c,transport,**change)
    assert transport.calls == []
    assert counts(c) == (0,0,0,0,0)


def test_caller_transaction_not_consumed(db):
    c,_ = db
    c.execute("BEGIN IMMEDIATE")
    transport = Fake(payload([]))
    with pytest.raises(ValueError):
        run(c,transport)
    assert c.in_transaction and transport.calls == []
    c.rollback()
    assert counts(c) == (0,0,0,0,0)


def test_operational_failure_propagates_and_rolls_back(db,monkeypatch):
    a = api()
    c,_ = db
    def fail(*args):
        raise sqlite3.OperationalError("simulated disk failure")
    monkeypatch.setattr(i,"append_fixture",fail)
    with pytest.raises(sqlite3.OperationalError):
        run(c,Fake(payload([fixture()])))
    assert counts(c) == (0,0,0,0,0)
    assert not c.in_transaction


def test_damaged_schema_denied_before_fetch(db):
    c,_ = db
    c.execute("DROP TRIGGER immutable_predictions_update")
    transport = Fake(payload([]))
    with pytest.raises(ValueError):
        run(c,transport)
    assert transport.calls == []


def test_transport_not_called_inside_writer_transaction(db):
    c,_ = db
    class Check:
        def fetch(self,url):
            assert not c.in_transaction
            return payload([fixture()])
    assert run(c,Check()).status == "SUCCEEDED"
