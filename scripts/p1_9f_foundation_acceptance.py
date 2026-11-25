"""Verify full P1.9e evidence on exact pinned online and offline replays.

Research only. No source rows persisted or printed, no model fitting,
no release certification. Existing offline guard is Python-level, not OS.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

from atp_gate.tml_cohort_manifest import cohort_manifest

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "docs/research/p1_9e_statistical_evidence_20261125.json"
FIELDS = ("manifest", "manifest_sha256", "eligible", "evaluation_folds",
          "aggregate", "folds", "bootstrap", "calendar_attribution", "evaluation_status")


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False)


def validate_replay_pair(online, offline, reference):
    """Check complete evidence equivalence, not merely aggregate metrics."""
    m = json.loads(canonical(cohort_manifest()))
    digest = hashlib.sha256(canonical(m).encode()).hexdigest()
    for name, result in (("online", online), ("offline", offline), ("reference", reference)):
        if not isinstance(result, dict) or any(key not in result for key in FIELDS):
            raise ValueError(f"{name} evidence missing required fields")
        if result.get("schema") != "TML_COHORT_MANIFEST_REPLAY_V3":
            raise ValueError(f"{name} schema mismatch")
        if (canonical(result["manifest"]) != canonical(m) or result["manifest_sha256"] != digest
                or result["eligible"] != m["expected_eligible"]
                or canonical(result["evaluation_folds"]) != canonical(m["evaluation_by_year"])
                or result["evaluation_status"] != m["evaluation_status"]):
            raise ValueError(f"{name} locked manifest mismatch")
        for flag in ("official_match_draw_verified","model_validation_trusted","allocation_enabled"):
            if result.get(flag) is not False:
                raise ValueError(f"{name} research boundary violated: {flag}")
        if type(result.get("stake")) is not int or result["stake"] != 0:
            raise ValueError(f"{name} nonzero or invalid stake")
        folds = result["folds"]
        metrics = ("global_elo_log_loss","surface_elo_log_loss","global_elo_brier",
                   "surface_elo_brier","coinflip_log_loss","coinflip_brier")
        if (not isinstance(folds,list) or len(folds)!=3 or
                any(not isinstance(f,dict) or any(k not in f for k in ("year","n",*metrics)) for f in folds)):
            raise ValueError(f"{name} missing fold metrics")
        if {str(f["year"]):f["n"] for f in folds} != m["evaluation_by_year"]:
            raise ValueError(f"{name} wrong fold support")
        if result["aggregate"].get("n") != m["expected_evaluated"]:
            raise ValueError(f"{name} aggregate support mismatch")
        bs = result["bootstrap"]
        if (bs.get("replicates")!=2000 or bs.get("seed")!=29
                or bs.get("status")!="EVENT_BOOTSTRAP_DESCRIPTIVE_ONLY"
                or bs.get("event_clusters")!=187
                or bs.get("cluster_unit")!="EVENT_ID"):
            raise ValueError(f"{name} uncertainty configuration drift")
        for key in ("global_elo_minus_coinflip_95ci","surface_elo_minus_coinflip_95ci",
                    "surface_elo_minus_global_elo_log_loss_95ci","surface_elo_minus_global_elo_brier_95ci"):
            ci = bs.get(key)
            if not isinstance(ci,list) or len(ci)!=2 or ci[0]>ci[1]:
                raise ValueError(f"{name} missing or invalid interval")
        receipts = result.get("source_receipts",[])
        if len(receipts)!=5 or {str(r["season"]) for r in receipts} != set(m["original_sha256"]):
            raise ValueError(f"{name} source receipt coverage mismatch")
        for rec in receipts:
            year = str(rec["season"])
            if (rec.get("raw_sha256")!=m["original_sha256"][year]
                    or rec.get("derived_sha256")!=m["derived_sha256"][year]):
                raise ValueError(f"{name} source hash mismatch")
            if name=="offline":
                if rec.get("acquisition_mode")!="LOCAL_PINNED_SNAPSHOT" or rec.get("actual_fetch_uri") is not None:
                    raise ValueError("offline must not claim network acquisition")
            else:
                expected_uri = (m["revised_2025_url"] if year=="2025" else
                    "https://api.github.com/repos/Tennismylife/TML-Database/git/blobs/"+m["original_git_blobs"][year])
                expected_mode = "PINNED_PUBLISHER_DOWNLOAD" if year=="2025" else "VERIFIED_GIT_BLOB"
                if rec.get("actual_fetch_uri")!=expected_uri or rec.get("acquisition_mode")!=expected_mode:
                    raise ValueError(f"{name} actual acquisition mismatch")
        if name=="offline":
            identity = result.get("identity_summary",{})
            if (identity.get("archived_2025_comparison")!="NOT_RUN_LOCAL_LOCKED_COHORT_ONLY"
                    or identity.get("old_multiple_name_ids") is not None):
                raise ValueError("offline archive comparison must remain unclaimed")
    for key in FIELDS:
        if canonical(online[key]) != canonical(offline[key]) or canonical(online[key]) != canonical(reference[key]):
            raise ValueError(f"full evidence drift: {key}")
    return {
        "status":"FOUNDATION_REPLAY_VERIFIED",
        "manifest_sha256":digest,
        "eligible":m["expected_eligible"],"evaluated":m["expected_evaluated"],
        "bootstrap_replicates":2000,"verified_fields":list(FIELDS),
        "evaluation_status":m["evaluation_status"],
        "independent_reviewer_verified":False,"official_match_draw_verified":False,
        "model_validation_trusted":False,"allocation_enabled":False,"stake":0,
    }


def main():
    reference = json.loads(REFERENCE.read_text(encoding="utf-8"))["result"]
    proc = subprocess.run([sys.executable,"-m","scripts.p1_9c_offline_replay_check"],
                          cwd=ROOT, check=True, text=True, capture_output=True, timeout=300)
    replay = json.loads(proc.stdout)
    if (replay.get("schema")!="P1_9C_OFFLINE_REAL_SOURCE_V1"
            or replay.get("socket_and_acquisition_functions_blocked_during_offline") is not True
            or replay.get("local_source_bytes_unchanged") is not True
            or replay.get("same_locked_results") is not True):
        raise ValueError("offline replay execution evidence missing")
    result = validate_replay_pair(replay["online"],replay["offline"],reference)
    print(json.dumps({"schema":"P1_9F_FOUNDATION_ACCEPTANCE_V1","acceptance":result,
                      "python_level_network_guard":True,"local_source_bytes_unchanged":True,
                      "online":replay["online"],"offline":replay["offline"]},
                     sort_keys=True),flush=True)


if __name__ == "__main__":
    main()
