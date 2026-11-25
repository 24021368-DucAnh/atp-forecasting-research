"""A2 synthetic authorization boundary: no external data or real permission."""
import importlib
import importlib.util

import pytest


def validate(request):
    spec = importlib.util.find_spec("atp_gate.p2_5_synthetic_gate")
    assert spec is not None, "synthetic authorization validator is missing"
    return importlib.import_module("atp_gate.p2_5_synthetic_gate").validate_synthetic_request(request)


def request_fixture():
    return {
        "mode": "SYNTHETIC_ONLY",
        "owner_id": "SYN-OWNER",
        "custodian_id": "SYN-CUSTODIAN",
        "owner_approved": True,
        "custodian_accepted": True,
        "freeze_date": "2099-01-01",
        "access_date": "2099-01-02",
        "start_date": "2099-02-01",
        "end_date": "2099-03-01",
        "protocol_sha256": "a" * 64,
        "model_sha256": "b" * 64,
    }


def test_synthetic_gate_never_authorizes_real_access():
    receipt = validate(request_fixture())
    assert receipt == {
        "status": "SIMULATION_ONLY",
        "real_data_authorized": False,
        "holdout_accessed": False,
        "model_validation_trusted": False,
        "allocation_enabled": False,
        "stake": 0,
    }


@pytest.mark.parametrize("field", list(request_fixture()))
def test_missing_required_field_is_rejected(field):
    request = request_fixture()
    del request[field]
    with pytest.raises(ValueError):
        validate(request)


@pytest.mark.parametrize("field,bad", [
    ("mode", "REAL_DATA"), ("mode", "HOLDOUT"),
    ("owner_approved", False), ("owner_approved", 1),
    ("custodian_accepted", False), ("custodian_accepted", "true"),
    ("custodian_id", "SYN-OWNER"), ("owner_id", "actual-owner"),
    ("custodian_id", ""), ("custodian_id", None),
    ("start_date", "2026-02-01"), ("start_date", "2027-02-01"),
    ("start_date", "2099-02-30"), ("start_date", "20990201"),
    ("end_date", "2099-02-01"), ("access_date", "2099-03-01"),
    ("freeze_date", "2099-01-03"), ("freeze_date", None),
    ("protocol_sha256", "a" * 63), ("protocol_sha256", "G" * 64),
    ("model_sha256", "A" * 64), ("model_sha256", 123),
])
def test_invalid_request_is_rejected(field, bad):
    request = request_fixture()
    request[field] = bad
    with pytest.raises(ValueError):
        validate(request)


@pytest.mark.parametrize("extra", ["source_url", "real_data_authorized", "outcomes", "holdout_path"])
def test_unknown_fields_cannot_expand_scope(extra):
    request = request_fixture()
    request[extra] = True
    with pytest.raises(ValueError):
        validate(request)


@pytest.mark.parametrize("bad", [None, [], "SYNTHETIC_ONLY"])
def test_non_mapping_is_rejected(bad):
    with pytest.raises(ValueError):
        validate(bad)
