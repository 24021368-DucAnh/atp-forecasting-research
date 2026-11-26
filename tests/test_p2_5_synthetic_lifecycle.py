"""A3 synthetic-only lifecycle; all inputs are invented and local."""
import hashlib
import importlib
import importlib.util
import json
import math
import re

import pytest


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


def session(request=None):
    spec = importlib.util.find_spec("atp_gate.p2_5_synthetic_lifecycle")
    assert spec is not None, "synthetic lifecycle is missing"
    cls = importlib.import_module("atp_gate.p2_5_synthetic_lifecycle").SyntheticSession
    return cls(request_fixture() if request is None else request)


def train():
    return [
        {"id": "SYN-T1", "feature": 0.1, "outcome": 0},
        {"id": "SYN-T2", "feature": 0.5, "outcome": 1},
        {"id": "SYN-T3", "feature": 0.9, "outcome": 1},
    ]


def matchups():
    return [{"id": "SYN-E1", "feature": 0.4}, {"id": "SYN-E2", "feature": 0.8}]


def labels():
    return [{"id": "SYN-E1", "outcome": 0}, {"id": "SYN-E2", "outcome": 1}]


def frozen():
    s = session()
    assert s.fit(train()) is None
    digest = s.freeze()
    assert re.fullmatch(r"[0-9a-f]{64}", digest)
    return s, digest


def predicted():
    s, digest = frozen()
    assert s.predict(matchups(), digest=digest) is None
    return s


def release(s, rows=None, role="SYN-CUSTODIAN"):
    return s.release(labels() if rows is None else rows, custodian_id=role)


def test_aggregate_only_happy_path():
    report = release(predicted(), list(reversed(labels())))
    assert set(report) == {
        "status", "real_data_authorized", "holdout_accessed",
        "model_validation_trusted", "allocation_enabled", "stake",
        "n", "coverage", "log_loss", "brier",
        "commitment_schema", "frozen_digest", "prediction_digest",
    }
    assert report["status"] == "SIMULATION_ONLY"
    for key in ("real_data_authorized", "holdout_accessed",
                "model_validation_trusted", "allocation_enabled"):
        assert report[key] is False
    assert report["stake"] == 0
    assert report["n"] == 2
    assert report["coverage"] == 1
    # Laplace smoothed low/high bin probabilities: 1/3 and 3/4.
    assert report["log_loss"] == pytest.approx(math.log(2) / 2)
    assert report["brier"] == pytest.approx(25 / 288)


def test_empty_bin_uses_prior():
    s = session()
    s.fit([{"id": "SYN-T1", "feature": 0.1, "outcome": 0}])
    d = s.freeze()
    s.predict([{"id": "SYN-E1", "feature": 0.5}], digest=d)
    report = release(s, [{"id": "SYN-E1", "outcome": 1}])
    assert report["log_loss"] == pytest.approx(math.log(2))
    assert report["brier"] == pytest.approx(0.25)


def test_freeze_digest_independent_of_training_order():
    s, d = frozen()
    other = session()
    other.fit(list(reversed(train())))
    assert other.freeze() == d


def test_freeze_digest_binds_training_state():
    _, d = frozen()
    other = session()
    rows = train()
    rows[0]["outcome"] = 1
    other.fit(rows)
    assert other.freeze() != d


def test_freeze_digest_binds_request_commitment():
    _, d = frozen()
    request = request_fixture()
    request["protocol_sha256"] = "c" * 64
    other = session(request)
    other.fit(train())
    assert other.freeze() != d


def test_session_copies_validated_request():
    request = request_fixture()
    s = session(request)
    request["custodian_id"] = "SYN-ATTACKER"
    s.fit(train())
    d = s.freeze()
    s.predict(matchups(), digest=d)
    with pytest.raises(ValueError):
        release(s, role="SYN-ATTACKER")
    assert release(s)["n"] == 2


def test_session_copies_training_and_prediction_inputs():
    s = session()
    rows = train()
    s.fit(rows)
    rows[0]["outcome"] = 1
    d = s.freeze()
    eval_rows = matchups()
    s.predict(eval_rows, digest=d)
    eval_rows[0]["feature"] = 0.9
    assert release(s)["brier"] == pytest.approx(25 / 288)


@pytest.mark.parametrize("field,value", [
    ("mode", "REAL_DATA"), ("owner_approved", False), ("custodian_id", "SYN-OWNER"),
])
def test_session_requires_valid_authorization(field, value):
    request = request_fixture()
    request[field] = value
    with pytest.raises(ValueError):
        session(request)


@pytest.mark.parametrize("bad", [
    [], None, {},
    [{"id": "REAL-1", "feature": 0.2, "outcome": 1}],
    [{"id": "SYN-T1", "feature": 0.2, "outcome": True}],
    [{"id": "SYN-T1", "feature": True, "outcome": 1}],
    [{"id": "SYN-T1", "feature": float("nan"), "outcome": 1}],
    [{"id": "SYN-T1", "feature": float("inf"), "outcome": 1}],
    [{"id": "SYN-T1", "feature": 10**400, "outcome": 1}],
    [{"id": "SYN-T1", "feature": -0.1, "outcome": 1}],
    [{"id": "SYN-T1", "feature": 1.1, "outcome": 1}],
    [{"id": "SYN-T1", "feature": 0.2, "outcome": 2}],
    [{"id": "SYN-T1", "feature": 0.2}],
    [{"id": "SYN-T1", "feature": 0.2, "outcome": 1, "source": "external"}],
    [{"id": "SYN-T1", "feature": 0.2, "outcome": 1}] * 2,
])
def test_invalid_training_does_not_advance_state(bad):
    s = session()
    with pytest.raises(ValueError):
        s.fit(bad)
    s.fit(train())
    assert re.fullmatch(r"[0-9a-f]{64}", s.freeze())


@pytest.mark.parametrize("bad", [
    [], None, {},
    [{"id": "SYN-E1", "feature": 0.2, "outcome": 1}],
    [{"id": "SYN-T1", "feature": 0.2}],
    [{"id": "SYN-E1", "feature": 0.2}] * 2,
    [{"id": "SYN-E1"}],
    [{"id": "SYN-E1", "feature": float("-inf")}],
    [{"id": "SYN-E1", "feature": True}],
    [{"id": "SYN-E1", "feature": "0.2"}],
    [{"id": "SYN-E1", "feature": 0.2, "winner_id": "SYN-X"}],
    [{"id": "REAL-1", "feature": 0.2}],
])
def test_invalid_prediction_does_not_advance_state(bad):
    s, d = frozen()
    with pytest.raises(ValueError):
        s.predict(bad, digest=d)
    s.predict(matchups(), digest=d)
    assert release(s)["n"] == 2


@pytest.mark.parametrize("bad", [
    [], None, {},
    [{"id": "SYN-E1", "outcome": 0}],
    [{"id": "SYN-E1", "outcome": 0}, {"id": "SYN-OTHER", "outcome": 1}],
    [{"id": "SYN-E1", "outcome": 0}] * 2,
    [{"id": "SYN-E1", "outcome": False}, {"id": "SYN-E2", "outcome": 1}],
    [{"id": "SYN-E1", "outcome": 0, "feature": 0.4}, {"id": "SYN-E2", "outcome": 1}],
    [{"id": "SYN-E1", "outcome": 0}, {"id": "SYN-E2", "outcome": 1},
     {"id": "SYN-E3", "outcome": 1}],
])
def test_invalid_labels_do_not_consume_release(bad):
    s = predicted()
    with pytest.raises(ValueError):
        s.release(bad, custodian_id="SYN-CUSTODIAN")
    assert release(s)["n"] == 2


def test_wrong_digest_does_not_advance_state():
    s, d = frozen()
    with pytest.raises(ValueError):
        s.predict(matchups(), digest="0" * 64)
    s.predict(matchups(), digest=d)
    assert release(s)["n"] == 2


def test_wrong_role_does_not_consume_release():
    s = predicted()
    with pytest.raises(ValueError):
        release(s, role="SYN-OWNER")
    assert release(s)["n"] == 2


def test_state_order_and_one_time_release():
    s = session()
    with pytest.raises(ValueError):
        s.freeze()
    with pytest.raises(ValueError):
        s.predict(matchups(), digest="0" * 64)
    with pytest.raises(ValueError):
        release(s)
    s.fit(train())
    with pytest.raises(ValueError):
        s.fit(train())
    d = s.freeze()
    with pytest.raises(ValueError):
        s.freeze()
    with pytest.raises(ValueError):
        s.fit(train())
    with pytest.raises(ValueError):
        release(s)
    s.predict(matchups(), digest=d)
    with pytest.raises(ValueError):
        s.predict(matchups(), digest=d)
    assert release(s)["n"] == 2
    with pytest.raises(ValueError):
        release(s)
    with pytest.raises(ValueError):
        s.fit(train())


def test_release_binds_frozen_model_and_prediction_map():
    s, d = frozen()
    s.predict(matchups(), digest=d)
    report = release(s)
    assert report["commitment_schema"] == "SYNTHETIC_TWO_BIN_V2"
    assert report["frozen_digest"] == d
    # Independent literal fixture, not the implementation's hashing helper.
    payload = {"schema": "SYNTHETIC_PREDICTIONS_V2", "frozen_digest": d,
               "predictions": {"SYN-E1": 1 / 3, "SYN-E2": 3 / 4}}
    expected = hashlib.sha256(json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")).hexdigest()
    assert report["prediction_digest"] == expected


@pytest.mark.parametrize("bad", [0.999999, float("nan"), True])
def test_prediction_mutation_rejected_before_scoring(bad):
    s = predicted()
    original = s._predictions["SYN-E1"]
    s._predictions["SYN-E1"] = bad
    with pytest.raises(ValueError):
        release(s)
    s._predictions["SYN-E1"] = original
    assert release(s)["n"] == 2


def test_prediction_key_mutation_rejected_even_if_labels_match():
    s = predicted()
    s._predictions["SYN-E3"] = s._predictions.pop("SYN-E2")
    changed = [{"id": "SYN-E1", "outcome": 0}, {"id": "SYN-E3", "outcome": 1}]
    with pytest.raises(ValueError):
        release(s, changed)


@pytest.mark.parametrize("left,right", [(0, 0.0), (0.0, -0.0), (1, 1.0)])
def test_numeric_feature_equivalence_preserves_frozen_digest(left, right):
    a, b = session(), session()
    a.fit([{"id": "SYN-T1", "feature": left, "outcome": 0}])
    b.fit([{"id": "SYN-T1", "feature": right, "outcome": 0}])
    assert a.freeze() == b.freeze()


def test_distinct_features_in_same_bin_remain_distinct_commitments():
    a, b = session(), session()
    a.fit([{"id": "SYN-T1", "feature": 0.1, "outcome": 0}])
    b.fit([{"id": "SYN-T1", "feature": 0.2, "outcome": 0}])
    assert a.freeze() != b.freeze()


def test_prediction_commitment_is_order_independent_but_key_sensitive():
    a, da = frozen()
    a.predict(matchups(), digest=da)
    ra = release(a)
    b, db = frozen()
    b.predict(list(reversed(matchups())), digest=db)
    rb = release(b)
    assert ra["prediction_digest"] == rb["prediction_digest"]
    c, dc = frozen()
    rows = matchups()
    rows[1]["id"] = "SYN-E3"
    c.predict(rows, digest=dc)
    rc = release(c, [{"id": "SYN-E1", "outcome": 0}, {"id": "SYN-E3", "outcome": 1}])
    assert ra["prediction_digest"] != rc["prediction_digest"]
