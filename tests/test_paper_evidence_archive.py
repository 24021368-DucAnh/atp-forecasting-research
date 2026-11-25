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


def test_nonempty_history_roundtrip_preserves_original_evidence(tmp_path):
    from datetime import timedelta
    from atp_gate.contracts import DecisionOutput
    from atp_gate.paper_ledger import record_selection, settle_selection, close_month
    from atp_gate.paper_cash_history import close_evidence_from_report, audit_cash_history
    book,opening,_,at=evidence()
    decision=DecisionOutput(decision="SELECT",side="A",stake=Decimal("10"),
        ev_lower=.05,p_lower=.6,market_probability=.5,reasons=[])
    book=record_selection(book,"synthetic-archive",decision,Decimal("1.90"),
        at+timedelta(days=1))
    book=settle_selection(book,"synthetic-archive","VOID",at+timedelta(days=1,hours=1))
    boundary=datetime(2027,1,31,17,tzinfo=timezone.utc)
    book,monthly=close_month(book,"2027-02")
    closes=[close_evidence_from_report(monthly,boundary)]
    before=audit_cash_history(book,opening,closes,boundary)
    saved=store_cash_evidence(tmp_path,book,opening,closes,boundary)
    after=verify_cash_evidence(tmp_path,saved["archive_sha256"])
    assert after["evidence_sha256"]==before["evidence_sha256"]
    assert after["match_journal_events"]==2
    assert after["closed_months"]==1
    assert Decimal(after["net_paper_result"])==0


def test_missing_nested_snapshot_field_cannot_be_inferred(tmp_path):
    report=store_cash_evidence(tmp_path,*evidence())
    raw=json.loads((tmp_path/(report["archive_sha256"]+".json")).read_bytes())
    del raw["book"]["journal"]
    changed=json.dumps(raw,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
    sha=hashlib.sha256(changed).hexdigest()
    (tmp_path/(sha+".json")).write_bytes(changed)
    with pytest.raises(ValueError,match="complete|canonical"):
        verify_cash_evidence(tmp_path,sha)


def test_failed_atomic_publication_leaves_no_partial_archive(tmp_path,monkeypatch):
    import os
    def fail(*args,**kwargs):
        raise OSError("synthetic filesystem failure")
    monkeypatch.setattr(os,"link",fail)
    with pytest.raises(OSError):
        store_cash_evidence(tmp_path,*evidence())
    assert not list(tmp_path.iterdir())
