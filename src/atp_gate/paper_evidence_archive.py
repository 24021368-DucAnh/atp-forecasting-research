"""Private content-addressed research evidence, not external authentication.

No live systems, network activity, payments, or allocation. The owner must
retain a trusted digest independently. A local filesystem is not immutable.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import stat
import tempfile
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from .paper_cash_history import (
    OpeningEvidence, MonthCloseEvidence, audit_cash_history,
)
from .paper_ledger import PaperBook

MAX_BYTES = 16 * 1024 * 1024
SCHEMA = "PAPER_EVIDENCE_ARCHIVE_V1"


class ArchiveEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    archive_schema: Literal["PAPER_EVIDENCE_ARCHIVE_V1"] = Field(alias="schema")
    book: PaperBook
    opening: OpeningEvidence
    closes: list[MonthCloseEvidence]
    as_of: AwareDatetime


def _encode(envelope: ArchiveEnvelope) -> bytes:
    return json.dumps(
        envelope.model_dump(mode="json", by_alias=True),
        sort_keys=True, ensure_ascii=False, allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate archive JSON key")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("nonfinite archive JSON constant")


def _decode(data: bytes) -> ArchiveEnvelope:
    if not 0 < len(data) <= MAX_BYTES:
        raise ValueError("archive size outside allowed limit")
    try:
        parsed = json.loads(
            data.decode("utf-8"), object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
        envelope = ArchiveEnvelope.model_validate(parsed)
        # Only the exact, complete representation produced by this version
        # is accepted. Missing fields cannot be supplied by model defaults.
        if _encode(envelope) != data:
            raise ValueError("archive is not a complete canonical V1 envelope")
        return envelope
    except (UnicodeError, RecursionError) as exc:
        raise ValueError("invalid archive encoding or structure") from exc


def _archive_path(root: Path, digest: str) -> Path:
    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise ValueError("expected archive SHA256 must be 64 lowercase hex characters")
    return Path(root) / (digest + ".json")


def _read(path: Path) -> bytes:
    try:
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise ValueError("archive symlink is not permitted")
        if not stat.S_ISREG(mode):
            raise ValueError("archive must be a regular local file")
        with path.open("rb") as handle:
            data = handle.read(MAX_BYTES + 1)
    except OSError as exc:
        raise ValueError("archive file is unavailable") from exc
    if not 0 < len(data) <= MAX_BYTES:
        raise ValueError("archive size outside allowed limit")
    return data


def verify_cash_evidence(root: Path, expected_sha256: str) -> dict:
    """Verify exact saved bytes against the owner's independently kept digest.

    Matching bytes and internal arithmetic do not establish real-world truth.
    The directory must be trusted and owner-controlled, not adversarial shared
    storage. This routine cannot prevent another process rewriting files.
    """
    path = _archive_path(root, expected_sha256)
    data = _read(path)
    digest = hashlib.sha256(data).hexdigest()
    if not hmac.compare_digest(digest, expected_sha256):
        raise ValueError("archive bytes differ from expected SHA256")
    envelope = _decode(data)
    report = audit_cash_history(
        envelope.book, envelope.opening, envelope.closes, envelope.as_of,
    )
    return {
        **report, "archive_schema": SCHEMA, "archive_sha256": digest,
        "archive_digest_matches": True, "external_authenticity_verified": False,
        "allocation_enabled": False, "stake": 0,
    }


def store_cash_evidence(
    root: Path, book: PaperBook, opening: OpeningEvidence,
    closes: Sequence[MonthCloseEvidence], as_of: datetime,
) -> dict:
    """Publish a validated archive without replacing any existing file.

    Same-directory temporary file plus hard-link publication avoids exposing
    a partial JSON file. Filesystems without hard links fail explicitly.
    No global index, latest pointer, or raw external source is written.
    """
    audit_cash_history(book, opening, closes, as_of)
    envelope = ArchiveEnvelope(
        schema=SCHEMA, book=book, opening=opening, closes=list(closes), as_of=as_of,
    )
    data = _encode(envelope)
    _decode(data)
    digest = hashlib.sha256(data).hexdigest()
    root = Path(root)
    path = _archive_path(root, digest)
    root.mkdir(parents=True, exist_ok=True)

    fd, temp_name = tempfile.mkstemp(prefix=".paper-evidence-", dir=root)
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temp, path)
        except FileExistsError:
            # Never replace a damaged or conflicting archive, even if the
            # caller could recreate the original bytes.
            if _read(path) != data:
                raise ValueError("existing archive differs; refused overwrite")
        return verify_cash_evidence(root, digest)
    finally:
        temp.unlink(missing_ok=True)
