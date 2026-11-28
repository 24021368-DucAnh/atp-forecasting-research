from dataclasses import replace
import pytest

NOW = '2026-11-28T12:00:00Z'
START = '2026-11-28T00:00:00Z'
END = '2026-11-29T00:00:00Z'
URL = 'https://synthetic.invalid/results'


def setup():
    from atp_lab.intake.policy import SourcePolicy, ApprovalReceipt, Request
    policy = SourcePolicy('SYN-feed', 'SYNTHETIC', 'APPROVED', 'a'*64,
                          START, END, (URL,), ('FETCH', 'RETAIN'), 30, 1048576)
    receipt = ApprovalReceipt('SYN-approval', policy.source_id, policy.digest,
                              START, END, True)
    receipt = replace(receipt, digest=receipt.computed_digest)
    return policy, receipt, Request(policy.source_id, URL, 'GET', 'FETCH')


def test_approved_exact_synthetic_request():
    from atp_lab.intake.policy import check_request, invoke_fake
    p, a, r = setup()
    assert check_request(p, a, r, now=NOW).allowed
    calls = []
    def fake(url):
        calls.append(url)
        return b'fictional'
    assert invoke_fake(p, a, r, now=NOW, transport=fake) == b'fictional'
    assert calls == [URL]


@pytest.mark.parametrize('case', ['discovery','revoked','unknown','expired','real',
    'wrong-source','wrong-origin','redirect','userinfo','query','method','operation',
    'malformed-clock','receipt-tamper','policy-tamper','not-approved','no-receipt',
    'future-receipt','bool-quota','excess-quota','expired-receipt'])
def test_denied_requests_never_invoke_transport(case):
    from atp_lab.intake.policy import check_request, invoke_fake
    p, a, r = setup()
    now = NOW
    if case == 'discovery': p = replace(p, status='DISCOVERY_ONLY')
    if case == 'revoked': p = replace(p, status='REVOKED')
    if case == 'unknown': p = None
    if case == 'expired': now = END
    if case == 'real':
        p = replace(p, source_id='REAL-feed', mode='REAL', endpoints=('https://example.com/results',))
        a = replace(a, source_id=p.source_id, policy_digest=p.digest)
        a = replace(a, digest=a.computed_digest)
        r = replace(r, source_id=p.source_id, url=p.endpoints[0])
    if case == 'wrong-source': r = replace(r, source_id='SYN-other')
    if case == 'wrong-origin': r = replace(r, url='https://other.invalid/results')
    if case == 'redirect': r = replace(r, url=URL+'/next')
    if case == 'userinfo': r = replace(r, url='https://synthetic.invalid@other.invalid/results')
    if case == 'query': r = replace(r, url=URL+'?secret=1')
    if case == 'method': r = replace(r, method='POST')
    if case == 'operation': r = replace(r, operation='TRAIN')
    if case == 'malformed-clock': now = '2026-11-28T12:00:00'
    if case == 'receipt-tamper': a = replace(a, digest='0'*64)
    if case == 'policy-tamper': p = replace(p, max_bytes=10)
    if case == 'not-approved': a = replace(a, approved=False, digest='')
    if case == 'no-receipt': a = None
    if case == 'future-receipt':
        a = replace(a, approved_at='2026-11-28T13:00:00Z'); a = replace(a, digest=a.computed_digest)
    if case == 'bool-quota': p = replace(p, max_requests=True)
    if case == 'excess-quota': r = replace(r, requests_used=30)
    if case == 'expired-receipt':
        a = replace(a, expires_at=NOW); a = replace(a, digest=a.computed_digest)
    calls = []
    def fake(url): calls.append(url); return b'fictional'
    d = check_request(p, a, r, now=now)
    assert not d.allowed and d.reason
    with pytest.raises(ValueError): invoke_fake(p, a, r, now=now, transport=fake)
    assert calls == []


def test_fake_response_is_bounded():
    from atp_lab.intake.policy import invoke_fake
    p, a, r = setup()
    with pytest.raises(ValueError):
        invoke_fake(p, a, r, now=NOW, transport=lambda _: b'x'*(p.max_bytes+1))
