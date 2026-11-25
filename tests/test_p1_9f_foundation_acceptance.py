"""Regression tests for the foundation acceptance evidence contract."""
import copy
import json
from pathlib import Path

import pytest

from scripts.p1_9f_foundation_acceptance import validate_replay_pair

ROOT = Path(__file__).resolve().parents[1]


def pair():
    ref = json.loads((ROOT/"docs/research/p1_9e_statistical_evidence_20261125.json").read_text(encoding="utf-8"))["result"]
    online = copy.deepcopy(ref)
    offline = copy.deepcopy(ref)
    for r in offline["source_receipts"]:
        r.update(acquisition_mode="LOCAL_PINNED_SNAPSHOT", actual_fetch_uri=None)
    offline["identity_summary"].update(old_multiple_name_ids=None,
        archived_2025_comparison="NOT_RUN_LOCAL_LOCKED_COHORT_ONLY")
    return online, offline, ref


def test_foundation_replay_accepts_full_equivalent_evidence():
    a,b,r = pair()
    result = validate_replay_pair(a,b,r)
    assert result["status"] == "FOUNDATION_REPLAY_VERIFIED"
    assert result["evaluated"] == 7694
    assert result["bootstrap_replicates"] == 2000
    assert result["model_validation_trusted"] is False


@pytest.mark.parametrize("key", ["folds", "bootstrap", "calendar_attribution"])
def test_missing_evidence_is_rejected(key):
    a,b,r = pair()
    del b[key]
    with pytest.raises(ValueError):
        validate_replay_pair(a,b,r)


def test_identical_aggregate_but_changed_fold_rejected():
    a,b,r = pair()
    b["folds"][0]["global_elo_log_loss"] += .01
    with pytest.raises(ValueError):
        validate_replay_pair(a,b,r)


def test_equal_online_offline_but_reference_drift_rejected():
    a,b,r = pair()
    for x in (a,b):
        x["bootstrap"]["surface_elo_minus_global_elo_log_loss_95ci"][0] += .01
    with pytest.raises(ValueError):
        validate_replay_pair(a,b,r)


def test_offline_cannot_claim_network_acquisition():
    a,b,r = pair()
    b["source_receipts"][0]["actual_fetch_uri"] = "https://example.invalid"
    with pytest.raises(ValueError):
        validate_replay_pair(a,b,r)


@pytest.mark.parametrize("field,value", [("stake",1),("model_validation_trusted",True),
                                      ("allocation_enabled",True),("official_match_draw_verified",True)])
def test_research_boundary_remains_fail_closed(field,value):
    a,b,r = pair()
    b[field] = value
    with pytest.raises(ValueError):
        validate_replay_pair(a,b,r)
