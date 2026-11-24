"""Private evidence archival regression tests; no external systems."""
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json

import pytest

from atp_gate.contracts import RiskState
from atp_gate.paper_ledger import PaperBook
from atp_gate.paper_cash_history import OpeningEvidence
from atp_gate.paper_evidence_archive import store_cash_evidence, verify_cash_evidence


AT = datetime(2026, 12, 31, 17, tzinfo=timezone.utc)


def evidence():
    book = PaperBook(risk=RiskState(
        month="2027-01", free_cash=Decimal("1000"), open_exposure=0,
        protected_cash=0, phase="NORMAL", selections_today=0,
        month_loss_realized=0, week_loss_realized=0,
        annual_negative_month_loss=0, seen_match_ids=[],
    ))
    return book, OpeningEvidence(at=AT, amount=Decimal("1000")), [], AT


def test_archive_roundtrip_idempotence_and_separate_digest(tmp_path):
    first = store_cash_evidence(tmp_path, *evidence())
    second = store_cash_evidence(tmp_path, *evidence())
    assert first["archive_sha256"] == second["archive_sha256"]
    assert first["archive_sha256"] != first["evidence_sha256"]
    files = list(tmp_path.glob("*.json"))
    assert len(files) == 1
    assert hashlib.sha256(files[0].read_bytes()).hexdigest() == first["archive_sha256"]
    report = verify_cash_evidence(tmp_path, first["archive_sha256"])
    assert report["cash_consistency_verified"] is True
    assert report["archive_sha256"] == first["archive_sha256"]
    assert report["external_authenticity_verified"] is False
    assert report["allocation_enabled"] is False and report["stake"] == 0


def test_changed_archive_rejected_and_not_overwritten(tmp_path):
    report = store_cash_evidence(tmp_path, *evidence())
    path = tmp_path / (report["archive_sha256"] + ".json")
    path.write_bytes(b"modified")
    with pytest.raises(ValueError):
        verify_cash_evidence(tmp_path, report["archive_sha256"])
    with pytest.raises(ValueError):
        store_cash_evidence(tmp_path, *evidence())
    assert path.read_bytes() == b"modified"


@pytest.mark.parametrize("digest", ["../escape", "a"*63, "A"*64, "z"*64])
def test_bad_digest_rejected(tmp_path, digest):
    with pytest.raises(ValueError):
        verify_cash_evidence(tmp_path, digest)


def test_invalid_balance_never_published(tmp_path):
    b,o,c,at = evidence()
    b = b.model_copy(update={"risk":b.risk.model_copy(update={"free_cash":Decimal("999")})})
    with pytest.raises(ValueError):
        store_cash_evidence(tmp_path,b,o,c,at)
    assert not list(tmp_path.iterdir())


def test_different_asof_creates_distinct_archive(tmp_path):
    from datetime import timedelta
    b,o,c,at = evidence()
    a = store_cash_evidence(tmp_path,b,o,c,at)
    z = store_cash_evidence(tmp_path,b,o,c,at+timedelta(minutes=1))
    assert a["archive_sha256"] != z["archive_sha256"]
    assert a["evidence_sha256"] == z["evidence_sha256"]
    assert len(list(tmp_path.glob("*.json"))) == 2


def test_duplicate_key_rejected_even_when_bytes_match_digest(tmp_path):
    report = store_cash_evidence(tmp_path,*evidence())
    data = (tmp_path/(report["archive_sha256"]+".json")).read_bytes()
    changed = b'{"schema":"unexpected",'+data.lstrip()[1:]
    sha = hashlib.sha256(changed).hexdigest()
    (tmp_path/(sha+".json")).write_bytes(changed)
    with pytest.raises(ValueError,match="duplicate"):
        verify_cash_evidence(tmp_path,sha)


def test_oversized_file_rejected_before_parse(tmp_path):
    data=b"x"*(16*1024*1024+1)
    sha=hashlib.sha256(data).hexdigest()
    (tmp_path/(sha+".json")).write_bytes(data)
    with pytest.raises(ValueError,match="size|limit"):
        verify_cash_evidence(tmp_path,sha)


def test_symlink_archive_rejected_if_supported(tmp_path):
    a=store_cash_evidence(tmp_path,*evidence())
    path=tmp_path/(a["archive_sha256"]+".json")
    moved=tmp_path/"original"
    path.rename(moved)
    try:
        path.symlink_to(moved)
    except OSError:
        pytest.skip("local filesystem does not permit symlinks")
    with pytest.raises(ValueError,match="symlink"):
        verify_cash_evidence(tmp_path,a["archive_sha256"])
