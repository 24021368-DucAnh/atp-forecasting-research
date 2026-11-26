"""S3.1: a rights-first adapter with no production transport."""
from dataclasses import replace
from hashlib import sha256
import socket

import pytest

FIXTURES = "https://synthetic.invalid/v1/fixtures"
RESULTS = "https://synthetic.invalid/v1/results"
PAYLOAD = b'{"fixtures":[]}'


def api():
    from atp_lab.ingestion import adapter
    return adapter


class FakeTransport:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def fetch(self, url):
        self.calls.append(url)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def policy(a, **kwargs):
    return replace(a.SourcePolicy("SYN-feed"), enabled=True, **kwargs)


def test_default_is_denied_without_transport_or_sleep():
    a = api()
    transport = FakeTransport(PAYLOAD)
    delays = []
    with pytest.raises(a.FetchBlocked):
        a.fetch_synthetic(a.SourcePolicy("SYN-feed"), FIXTURES, transport,
                          sleep=delays.append)
    assert transport.calls == delays == []


@pytest.mark.parametrize("change", [
    {"mode":"REAL"}, {"permission_status":"ALLOWED"}, {"source_id":"ATP"},
    {"source_id":"SYN-"}, {"enabled":False}, {"enabled":1},
])
def test_real_or_invalid_scope_denied_before_fetch(change):
    a = api()
    p = replace(a.SourcePolicy("SYN-feed",enabled=True), **change)
    transport = FakeTransport(PAYLOAD)
    delays = []
    with pytest.raises(a.FetchBlocked):
        a.fetch_synthetic(p,FIXTURES,transport,sleep=delays.append)
    assert transport.calls == delays == []


@pytest.mark.parametrize("url", [
    "http://synthetic.invalid/v1/fixtures",
    "https://synthetic.invalid/v1/fixtures?token=x",
    "https://synthetic.invalid/v1/fixtures#x",
    "https://synthetic.invalid:443/v1/fixtures",
    "https://user@synthetic.invalid/v1/fixtures",
    "https://synthetic.invalid.evil.test/v1/fixtures",
    "https://synthetic.invalid/v1/../v1/fixtures",
    "https://synthetic.invalid/v1/players",
    "https://example.com/fixtures",
])
def test_exact_url_allowlist_before_fetch(url):
    a = api()
    transport = FakeTransport(PAYLOAD)
    delays = []
    with pytest.raises(a.FetchBlocked):
        a.fetch_synthetic(policy(a),url,transport,sleep=delays.append)
    assert transport.calls == delays == []


@pytest.mark.parametrize("change", [
    {"max_attempts":0}, {"max_attempts":4}, {"max_attempts":True},
    {"max_bytes":0}, {"max_bytes":1048577}, {"max_bytes":1.5},
    {"allowed_urls":(FIXTURES,"https://example.com/")},
    {"allowed_urls":()}, {"allowed_urls":FIXTURES},
])
def test_invalid_resource_or_endpoint_policy_denied(change):
    a = api()
    transport = FakeTransport(PAYLOAD)
    delays = []
    with pytest.raises(a.FetchBlocked):
        a.fetch_synthetic(policy(a,**change),FIXTURES,transport,sleep=delays.append)
    assert transport.calls == delays == []


def test_source_specific_allowlist():
    a = api()
    transport = FakeTransport(PAYLOAD)
    with pytest.raises(a.FetchBlocked):
        a.fetch_synthetic(policy(a,allowed_urls=(RESULTS,)),FIXTURES,transport,
                          sleep=lambda _: None)
    assert transport.calls == []


def test_success_exact_payload_and_digest_no_network(monkeypatch):
    a = api()
    def forbidden(*args, **kwargs):
        pytest.fail("network access is not allowed")
    monkeypatch.setattr(socket,"socket",forbidden)
    monkeypatch.setattr(socket,"getaddrinfo",forbidden)
    transport = FakeTransport(PAYLOAD)
    delays = []
    fetched = a.fetch_synthetic(policy(a),FIXTURES,transport,sleep=delays.append)
    assert fetched.source_id == "SYN-feed"
    assert fetched.url == FIXTURES
    assert fetched.payload == PAYLOAD
    assert fetched.digest == sha256(PAYLOAD).hexdigest()
    assert fetched.attempts == 1
    assert transport.calls == [FIXTURES]
    assert delays == []


def test_transient_retry_bounded_exponential_backoff():
    a = api()
    transport = FakeTransport(a.TransientFetchError("temporary"),
                              a.TransientFetchError("temporary"),PAYLOAD)
    delays = []
    fetched = a.fetch_synthetic(policy(a,max_attempts=3),RESULTS,transport,
                                sleep=delays.append)
    assert fetched.attempts == 3
    assert transport.calls == [RESULTS]*3
    assert delays == [.25,.5]


def test_retry_exhaustion_no_extra_call_or_sleep():
    a = api()
    transport = FakeTransport(a.TransientFetchError("temporary"),
                              a.TransientFetchError("temporary"),PAYLOAD)
    delays = []
    with pytest.raises(a.TransientFetchError):
        a.fetch_synthetic(policy(a,max_attempts=2),FIXTURES,transport,
                          sleep=delays.append)
    assert transport.calls == [FIXTURES]*2
    assert delays == [.25]


def test_permanent_error_not_retried():
    a = api()
    transport = FakeTransport(a.PermanentFetchError("permanent"),PAYLOAD)
    delays = []
    with pytest.raises(a.PermanentFetchError):
        a.fetch_synthetic(policy(a),FIXTURES,transport,sleep=delays.append)
    assert transport.calls == [FIXTURES]
    assert delays == []


@pytest.mark.parametrize("bad", [b"", "text", bytearray(b"x"), None])
def test_invalid_payload_not_retried(bad):
    a = api()
    transport = FakeTransport(bad,PAYLOAD)
    delays = []
    with pytest.raises(a.InvalidPayload):
        a.fetch_synthetic(policy(a),FIXTURES,transport,sleep=delays.append)
    assert transport.calls == [FIXTURES]
    assert delays == []


def test_payload_limit_exact_boundary():
    a = api()
    transport = FakeTransport(b"abc")
    fetched = a.fetch_synthetic(policy(a,max_bytes=3),FIXTURES,transport,
                                sleep=lambda _: None)
    assert fetched.payload == b"abc"
    transport = FakeTransport(b"abcd",PAYLOAD)
    delays = []
    with pytest.raises(a.InvalidPayload):
        a.fetch_synthetic(policy(a,max_bytes=3),FIXTURES,transport,sleep=delays.append)
    assert transport.calls == [FIXTURES]
    assert delays == []
