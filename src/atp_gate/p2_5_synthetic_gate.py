"""P2.5 synthetic-only contract simulation; not an authentication boundary."""
from datetime import date
import re

_FIELDS = frozenset({
    "mode", "owner_id", "custodian_id", "owner_approved", "custodian_accepted",
    "freeze_date", "access_date", "start_date", "end_date",
    "protocol_sha256", "model_sha256",
})


def validate_synthetic_request(request: dict) -> dict:
    """Validate simulated declarations; never authorize real data or a holdout."""
    if type(request) is not dict or request.keys() != _FIELDS:
        raise ValueError("invalid synthetic request schema")
    if request["mode"] != "SYNTHETIC_ONLY":
        raise ValueError("only synthetic mode is permitted")
    if request["owner_approved"] is not True or request["custodian_accepted"] is not True:
        raise ValueError("simulated approvals required")
    for field in ("owner_id", "custodian_id"):
        value = request[field]
        if type(value) is not str or re.fullmatch(r"SYN-[A-Z0-9]+(?:-[A-Z0-9]+)*", value) is None:
            raise ValueError("invalid synthetic role identifier")
    if request["owner_id"] == request["custodian_id"]:
        raise ValueError("synthetic roles must be distinct")
    dates = []
    for field in ("freeze_date", "access_date", "start_date", "end_date"):
        value = request[field]
        if type(value) is not str or re.fullmatch(r"2099-[0-9]{2}-[0-9]{2}", value) is None:
            raise ValueError("fictional year 2099 required")
        dates.append(date.fromisoformat(value))
    freeze, access, start, end = dates
    if not freeze <= access < start < end:
        raise ValueError("invalid synthetic reservation sequence")
    for field in ("protocol_sha256", "model_sha256"):
        value = request[field]
        if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError("invalid synthetic commitment")
    return {
        "status": "SIMULATION_ONLY",
        "real_data_authorized": False,
        "holdout_accessed": False,
        "model_validation_trusted": False,
        "allocation_enabled": False,
        "stake": 0,
    }
