"""S3.2: strict synthetic parsing and explicit source-scoped resolution."""
from contextlib import closing
from dataclasses import replace
from hashlib import sha256
import json

import pytest

from atp_lab.database import identity as i, forecast as f
from atp_lab.database.connection import open_reader, open_writer
from atp_lab.database.migrations import migrate
from atp_lab.ingestion.adapter import FetchedPayload, FIXTURES_ENDPOINT, RESULTS_ENDPOINT

OBS = "2026-01-02T13:00:00Z"
AVAILABLE = "2026-01-02T13:05:00Z"
START = "2026-01-02T10:00:00Z"
DONE = "2026-01-02T12:00:00Z"


def api():
    from atp_lab.ingestion import parser
    return parser


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "parser.sqlite"
    with closing(open_writer(path)) as c:
        migrate(c)
        i.migrate_identity(c)
        f.migrate_forecast(c)
        c.execute("BEGIN IMMEDIATE")
        for source in ("SYN-feed","SYN-other"):
            i.put_source(c,i.Source(source,"SYNTHETIC","LOCKED"))
        for player in ("SYN-A","SYN-B","SYN-C"):
            i.put_player(c,i.Player(player))
        i.put_tournament(c,i.Tournament("SYN-t","SYN-event","2026","ATP250","HARD"))
        i.put_match(c,i.Match("SYN-m","SYN-t","SYN-A","SYN-B"))
        i.put_match(c,i.Match("SYN-m2","SYN-t","SYN-A","SYN-C"))
        for alias, player in (("a","SYN-A"),("b","SYN-B"),("c","SYN-C")):
            i.put_alias(c,i.PlayerAlias("SYN-feed",alias,player))
        i.put_match_alias(c,i.MatchAlias("SYN-feed","m","SYN-m"))
        i.put_match_alias(c,i.MatchAlias("SYN-feed","m-alt","SYN-m"))
        i.put_match_alias(c,i.MatchAlias("SYN-other","m","SYN-m2"))
        i.put_alias(c,i.PlayerAlias("SYN-other","a","SYN-A"))
        i.put_alias(c,i.PlayerAlias("SYN-other","b","SYN-C"))
        c.commit()
    with closing(open_reader(path)) as reader:
        yield reader


def fixture(**change):
    return dict({"match_id":"m","player_1":"b","player_2":"a","revision":1,
                 "scheduled_start":START,"state":"SCHEDULED"}, **change)


def result(**change):
    return dict({"match_id":"m","player_1":"b","player_2":"a","revision":1,
                 "published_at":DONE,"actual_start":START,
                 "state":"COMPLETED","winner":"a"}, **change)


def fetched(rows=None, *, kind="fixtures", source="SYN-feed", raw=None):
    payload = raw if raw is not None else json.dumps({kind:rows}).encode("utf-8")
    url = FIXTURES_ENDPOINT if kind == "fixtures" else RESULTS_ENDPOINT
    return FetchedPayload(source,url,payload,sha256(payload).hexdigest(),1)


def parse(db, receipt, **kwargs):
    return api().parse_batch(db,receipt,observed_at=kwargs.get("observed_at",OBS),
                             available_at=kwargs.get("available_at",AVAILABLE))


def test_fixture_canonical_order_and_read_only(db):
    batch = parse(db,fetched([fixture()]))
    assert len(batch.fixtures) == 1 and batch.results == ()
    row = batch.fixtures[0]
    assert isinstance(row,i.Fixture)
    assert (row.match_id,row.player_a,row.player_b) == ("SYN-m","SYN-A","SYN-B")
    assert row.source_id == "SYN-feed"
    assert row.snapshot_id == batch.snapshot.snapshot_id
    assert batch.snapshot.digest == fetched([fixture()]).digest
    assert row.observed_at == "2026-01-02T13:00:00.000000Z"
    assert row.available_at == "2026-01-02T13:05:00.000000Z"
    assert row.scheduled_start == "2026-01-02T10:00:00.000000Z"
    assert db.execute("SELECT count(*) FROM source_snapshots").fetchone()[0] == 0
    assert db.execute("SELECT count(*) FROM fixture_versions").fetchone()[0] == 0


def test_result_winner_maps_to_canonical_player(db):
    batch = parse(db,fetched([result()],kind="results"))
    row = batch.results[0]
    assert isinstance(row,i.Result)
    assert batch.fixtures == ()
    assert row.winner == "SYN-A" and row.match_id == "SYN-m"
    assert row.published_at == "2026-01-02T12:00:00.000000Z"
    assert row.actual_start == "2026-01-02T10:00:00.000000Z"


def test_source_scoped_crosswalk(db):
    row = parse(db,fetched([fixture()],source="SYN-other")).fixtures[0]
    assert (row.match_id,row.player_a,row.player_b) == ("SYN-m2","SYN-A","SYN-C")


def test_unknown_clocks_stay_null(db):
    row = parse(db,fetched([result(published_at=None,actual_start=None)],kind="results"),
                available_at=None).results[0]
    assert row.published_at is row.actual_start is row.available_at is None


def test_ids_are_deterministic_and_revision_specific(db):
    receipt = fetched([fixture()])
    first = parse(db,receipt)
    again = parse(db,receipt,observed_at="2026-01-02T20:00:00+07:00")
    assert first == again
    changed = parse(db,fetched([fixture(revision=2)]))
    assert first.snapshot.snapshot_id != changed.snapshot.snapshot_id
    assert first.fixtures[0].fixture_id != changed.fixtures[0].fixture_id
    later = parse(db,receipt,observed_at="2026-01-02T13:01:00Z")
    assert later.snapshot.snapshot_id != first.snapshot.snapshot_id
    assert later.fixtures[0].fixture_id == first.fixtures[0].fixture_id


def test_empty_batch_is_valid(db):
    batch = parse(db,fetched([]))
    assert batch.fixtures == batch.results == ()


@pytest.mark.parametrize("raw", [
    b"not-json", b"\xff", b"[]", b'{"fixtures":[],"fixtures":[]}',
    b'{"fixtures":[{"revision":1,"revision":2}]}',
    b'{"fixtures":[],"unexpected":true}', b'{"results":[]}',
    b'{"fixtures":null}', b'{"fixtures":[NaN]}',
    b'{"fixtures":[' + b'['*1100 + b'0' + b']'*1100 + b']}', 
])
def test_invalid_json_rejected(db,raw):
    a = api()
    with pytest.raises(a.ParseError):
        parse(db,fetched(raw=raw))


@pytest.mark.parametrize("change", [
    {"match_id":"unknown"}, {"player_1":"unknown"}, {"player_1":"a"},
    {"player_1":"c"}, {"revision":True}, {"revision":0},
    {"revision":1.5}, {"state":"LIVE"}, {"scheduled_start":None},
    {"scheduled_start":"2026-02-30T10:00:00Z"},
    {"scheduled_start":"2026-01-02T10:00:00"},
    {"match_id":""}, {"match_id":"m\u0000"}, {"unexpected":"x"},
])
def test_invalid_fixture_rejected(db,change):
    a = api()
    with pytest.raises(a.ParseError):
        parse(db,fetched([fixture(**change)]))


@pytest.mark.parametrize("change", [
    {"winner":"c"}, {"winner":None}, {"state":"VOID","winner":"a"},
    {"published_at":"2026-01-03T12:00:00Z"},
    {"actual_start":"2026-01-02T12:30:00Z"},
    {"state":"UNRECOGNIZED"}, {"player_1":"c"},
])
def test_invalid_result_rejected(db,change):
    a = api()
    with pytest.raises(a.ParseError):
        parse(db,fetched([result(**change)],kind="results"))


def test_required_field_missing_rejected(db):
    a = api()
    row = fixture()
    del row["scheduled_start"]
    with pytest.raises(a.ParseError):
        parse(db,fetched([row]))


def test_unknown_source_rejected(db):
    a = api()
    with pytest.raises(a.ParseError):
        parse(db,fetched([fixture()],source="SYN-unknown"))


def test_duplicate_canonical_revision_via_alias_rejected(db):
    a = api()
    with pytest.raises(a.ParseError):
        parse(db,fetched([fixture(),fixture(match_id="m-alt")]))


@pytest.mark.parametrize("change", [
    {"digest":"0"*64}, {"url":"https://example.com/fixtures"},
    {"attempts":0}, {"attempts":True}, {"source_id":"REAL"},
])
def test_forged_receipt_rejected(db,change):
    a = api()
    with pytest.raises(a.ParseError):
        parse(db,replace(fetched([fixture()]),**change))


@pytest.mark.parametrize("clocks", [
    {"observed_at":"2026-01-02T13:00:00"},
    {"available_at":"2026-01-02T12:59:00Z"},
    {"available_at":"2026-01-02T13:05:00-00:00"},
])
def test_invalid_local_clock_rejected(db,clocks):
    a = api()
    with pytest.raises(a.ParseError):
        parse(db,fetched([fixture()]),**clocks)


def test_batch_row_limit(db):
    a = api()
    with pytest.raises(a.ParseError):
        parse(db,fetched([fixture(revision=n+1) for n in range(1001)]))
