"""Pure, fail-closed policy for fictional requests; no network client."""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import re


def _digest(value):
    return sha256(_json(value)).hexdigest()


def _json(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def _id(value):
    return type(value) is str and re.fullmatch(r'SYN-[A-Za-z0-9._:-]{1,120}',value) is not None


def _hex(value):
    return type(value) is str and re.fullmatch(r'[0-9a-f]{64}',value) is not None


def _clock(value):
    if type(value) is not str or not re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ',value):
        raise ValueError('canonical UTC seconds required')
    return datetime.fromisoformat(value[:-1]+'+00:00')


def _url(value):
    return type(value) is str and re.fullmatch(r'https://synthetic\.invalid/[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*',value) is not None


@dataclass(frozen=True)
class SourcePolicy:
    source_id: str
    mode: str = 'DISCOVERY'
    status: str = 'DISCOVERY_ONLY'
    terms_digest: str = ''
    reviewed_at: str = ''
    expires_at: str = ''
    endpoints: tuple[str,...] = ()
    operations: tuple[str,...] = ()
    max_requests: int = 0
    max_bytes: int = 0

    @property
    def digest(self):
        return _digest(asdict(self))


@dataclass(frozen=True)
class ApprovalReceipt:
    approval_id: str
    source_id: str
    policy_digest: str
    approved_at: str
    expires_at: str
    approved: bool
    digest: str = ''

    @property
    def computed_digest(self):
        value=asdict(self);value.pop('digest')
        return _digest(value)


@dataclass(frozen=True)
class Request:
    source_id: str
    url: str
    method: str
    operation: str
    requests_used: int = 0


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str


def check_request(policy, receipt, request, *, now):
    """Only test-domain requests; receipt is not real authorization."""
    deny=Decision(False,'BLOCKED')
    try:
        if (type(policy) is not SourcePolicy or type(receipt) is not ApprovalReceipt
            or type(request) is not Request or not _id(policy.source_id)
            or policy.mode!='SYNTHETIC' or policy.status!='APPROVED'
            or not _hex(policy.terms_digest) or not _id(receipt.approval_id)
            or receipt.approved is not True or receipt.source_id!=policy.source_id
            or request.source_id!=policy.source_id
            or type(policy.endpoints) is not tuple or not policy.endpoints
            or not all(_url(x) for x in policy.endpoints)
            or type(policy.operations) is not tuple or not policy.operations
            or any(x not in ('FETCH','RETAIN','NORMALIZE') for x in policy.operations)
            or type(policy.max_requests) is not int or not 1<=policy.max_requests<=30
            or type(policy.max_bytes) is not int or not 1<=policy.max_bytes<=1048576
            or type(request.requests_used) is not int or not 0<=request.requests_used<policy.max_requests
            or request.method!='GET' or request.operation not in policy.operations
            or not _url(request.url) or request.url not in policy.endpoints
            or receipt.policy_digest!=policy.digest or receipt.digest!=receipt.computed_digest):
            return deny
        t=_clock(now);reviewed=_clock(policy.reviewed_at);expires=_clock(policy.expires_at)
        approved=_clock(receipt.approved_at);end=_clock(receipt.expires_at)
        if not reviewed<=approved<=t<end<=expires:
            return deny
    except (ValueError,TypeError,OverflowError,AttributeError):
        return deny
    return Decision(True,'SYNTHETIC_ONLY')


def invoke_fake(policy, receipt, request, *, now, transport):
    """Trusted injected test double only. No redirect or network support."""
    if not check_request(policy,receipt,request,now=now).allowed or request.operation!='FETCH':
        raise ValueError('synthetic fetch blocked')
    payload=transport(request.url)
    if type(payload) is not bytes or not 0<len(payload)<=policy.max_bytes:
        raise ValueError('invalid fake response size/type')
    return payload
