"""Rights-first synthetic adapter. No real network transport is provided."""
from dataclasses import dataclass
from hashlib import sha256
import re
from typing import Callable, Protocol

FIXTURES_ENDPOINT = "https://synthetic.invalid/v1/fixtures"
RESULTS_ENDPOINT = "https://synthetic.invalid/v1/results"
SYNTHETIC_ENDPOINTS = (FIXTURES_ENDPOINT, RESULTS_ENDPOINT)
MAX_ATTEMPTS = 3
MAX_BYTES = 1048576
_SOURCE_ID = re.compile(r"SYN-[A-Za-z0-9._:-]+")


class FetchBlocked(ValueError):
    """Policy or endpoint is not eligible for synthetic fetching."""


class TransientFetchError(RuntimeError):
    """Trusted fake transport reports a retryable failure."""


class PermanentFetchError(RuntimeError):
    """Trusted fake transport reports a non-retryable failure."""


class InvalidPayload(ValueError):
    """Fake transport returned invalid or oversized bytes."""


class SyntheticTransport(Protocol):
    """Trusted in-memory fake transport; endpoint is an opaque lookup key."""

    def fetch(self, url: str) -> bytes:
        ...


@dataclass(frozen=True)
class SourcePolicy:
    source_id: str
    mode: str = "SYNTHETIC"
    permission_status: str = "LOCKED"
    enabled: bool = False
    allowed_urls: tuple[str, ...] = SYNTHETIC_ENDPOINTS
    max_attempts: int = MAX_ATTEMPTS
    max_bytes: int = MAX_BYTES


@dataclass(frozen=True)
class FetchedPayload:
    source_id: str
    url: str
    payload: bytes
    digest: str
    attempts: int


def _check_policy(policy: SourcePolicy, url: str) -> None:
    # The opt-in enables only fake inputs, not external source rights.
    if (type(policy) is not SourcePolicy
            or policy.enabled is not True
            or type(policy.source_id) is not str
            or _SOURCE_ID.fullmatch(policy.source_id) is None
            or type(policy.mode) is not str
            or policy.mode != "SYNTHETIC"
            or type(policy.permission_status) is not str
            or policy.permission_status != "LOCKED"):
        raise FetchBlocked("synthetic scope not enabled")
    if (type(policy.max_attempts) is not int
            or not 1 <= policy.max_attempts <= MAX_ATTEMPTS
            or type(policy.max_bytes) is not int
            or not 1 <= policy.max_bytes <= MAX_BYTES):
        raise FetchBlocked("invalid synthetic resource policy")
    allowed = policy.allowed_urls
    if (type(allowed) is not tuple or not allowed
            or any(type(item) is not str or item not in SYNTHETIC_ENDPOINTS
                   for item in allowed)
            or type(url) is not str
            or url not in allowed):
        raise FetchBlocked("synthetic endpoint not allowed")


def fetch_synthetic(policy: SourcePolicy, url: str,
                    transport: SyntheticTransport, *,
                    sleep: Callable[[float], None]) -> FetchedPayload:
    """Fetch bounded fake bytes after a fail-closed policy check.

    The injected transport and sleep callback must be trusted local
    test doubles. This is not a sandbox for arbitrary caller code.
    No external network client, redirect handling or real rights path
    is implemented. The byte limit applies to returned in-memory data.
    """
    _check_policy(policy, url)
    for attempt in range(1, policy.max_attempts + 1):
        try:
            payload = transport.fetch(url)
        except TransientFetchError:
            if attempt == policy.max_attempts:
                raise
            sleep(0.25 * 2 ** (attempt - 1))
            continue
        if type(payload) is not bytes or not 1 <= len(payload) <= policy.max_bytes:
            raise InvalidPayload("invalid synthetic payload type or size")
        return FetchedPayload(policy.source_id, url, payload,
                              sha256(payload).hexdigest(), attempt)
    raise AssertionError("unreachable synthetic retry state")
