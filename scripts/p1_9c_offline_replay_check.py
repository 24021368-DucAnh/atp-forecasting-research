"""Private actual-source online/offline comparison, no raw data retained."""
import hashlib
import json
from pathlib import Path
import socket
import tempfile
from unittest.mock import patch

from atp_gate.tml_cohort_manifest import cohort_manifest
from scripts import p1_8c_cohort_research as replay


def deny_network(*args, **kwargs):
    raise AssertionError("offline replay attempted a network operation")


def main():
    manifest = cohort_manifest()
    with tempfile.TemporaryDirectory(prefix="p1-9c-offline-check-") as temp:
        root = Path(temp)
        current, _, receipts = replay.acquire_sources(manifest, root / "fetch")
        local = root / "local"
        local.mkdir()
        for year, raw in sorted(current.items()):
            (local / f"{year}-{manifest['original_sha256'][year]}.csv").write_bytes(raw)
        # Run with real local files and prohibit both acquisition functions and
        # socket/DNS operations. This is a test guard, not an OS-level sandbox.
        with patch.object(replay, "verified_blob", deny_network), \
             patch.object(replay, "update_tml_season", deny_network), \
             patch.object(socket.socket, "connect", deny_network), \
             patch.object(socket.socket, "connect_ex", deny_network), \
             patch.object(socket, "create_connection", deny_network), \
             patch.object(socket, "getaddrinfo", deny_network):
            offline = replay.run_replay(local_dir=local)
        online = replay.run_replay()
        for key in ("manifest_sha256", "eligible", "evaluation_folds", "aggregate"):
            if offline[key] != online[key]:
                raise ValueError("offline/online locked result mismatch")
        for rec in offline["source_receipts"]:
            year = rec["season"]
            if (rec["acquisition_mode"] != "LOCAL_PINNED_SNAPSHOT"
                    or rec["actual_fetch_uri"] is not None
                    or rec["raw_sha256"] != manifest["original_sha256"][year]
                    or rec["derived_sha256"] != manifest["derived_sha256"][year]):
                raise ValueError("offline acquisition receipt mismatch")
        for rec in online["source_receipts"]:
            year = rec["season"]
            if rec["actual_fetch_uri"] != receipts[year]["actual_fetch_uri"]:
                raise ValueError("online acquisition receipt mismatch")
        for year, digest in manifest["original_sha256"].items():
            if hashlib.sha256((local / f"{year}-{digest}.csv").read_bytes()).hexdigest() != digest:
                raise ValueError("local source changed during replay")
        if offline["identity_summary"]["archived_2025_comparison"] != "NOT_RUN_LOCAL_LOCKED_COHORT_ONLY":
            raise ValueError("offline archive review must not claim execution")
        print(json.dumps({
            "schema":"P1_9C_OFFLINE_REAL_SOURCE_V1",
            "online":online, "offline":offline,
            "socket_and_acquisition_functions_blocked_during_offline":True,
            "local_source_bytes_unchanged":True,
            "same_locked_results":True,
            "model_validation_trusted":False,"allocation_enabled":False,"stake":0
        },sort_keys=True),flush=True)


if __name__ == "__main__":
    main()
