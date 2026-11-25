"""One-off reproduction of the fixed TML historical skill study.
No source CSV is redistributed; output contains aggregate metadata only.
"""
from __future__ import annotations
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from urllib.request import Request, urlopen

PINS = {
    2021: "2bd4eaf4eb28a09b42ab4ecd5830a8f3ad068faa",
    2022: "2b6726106fefb22b40c2816e4c703a48e9d312be",
    2023: "5ceb7397e3a217e51f197c9e83ea435faf690eeb",
    2024: "cf513429259b4a15e84e2021206895d9bd4ff772",
    2025: "1aff9b077cf4de7806b665ec0c6d8b4032a040f3",
}
MAX_BYTES = 20 * 1024 * 1024


def verified_blob(sha):
    url = f"https://api.github.com/repos/Tennismylife/TML-Database/git/blobs/{sha}"
    request = Request(url, headers={"Accept": "application/vnd.github+json",
                                    "User-Agent": "private-research-reproduction"})
    with urlopen(request, timeout=40) as response:
        if response.geturl() != url:
            raise ValueError("unexpected source redirect")
        raw = response.read(MAX_BYTES * 2 + 1)
    if len(raw) > MAX_BYTES * 2:
        raise ValueError("oversized source response")
    record = json.loads(raw)
    if record.get("sha") != sha or record.get("encoding") != "base64":
        raise ValueError("wrong source blob identity or encoding")
    data = base64.b64decode("".join(record["content"].split()), validate=True)
    if not 0 < len(data) <= MAX_BYTES or len(data) != record["size"]:
        raise ValueError("source size mismatch")
    actual = hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()
    if actual != sha:
        raise ValueError("source Git object hash mismatch")
    return data


def main():
    with tempfile.TemporaryDirectory(prefix="tml-reproduction-") as folder:
        root = Path(folder)
        paths = []
        for year, pin in PINS.items():
            data = verified_blob(pin)
            sha = hashlib.sha256(data).hexdigest()
            path = root / f"{year}-{sha}.csv"
            path.write_bytes(data)
            paths.append(str(path))
            print(f"verified source {year}: blob={pin}, sha256={sha}, bytes={len(data)}", flush=True)
        output = root / "report.json"
        subprocess.run([sys.executable, "-m", "atp_gate", "tml-elo-experiment",
                        *paths, "--out", str(output)], check=True)
        report = json.loads(output.read_text(encoding="utf-8"))
        if report["status"] != "HISTORICAL_SKILL_RESEARCH_ONLY":
            raise ValueError("unexpected report status")
        if report["holdout_years"] != [2023, 2024, 2025]:
            raise ValueError("unexpected holdout years")
        for flag in ("t60_quote_verified", "market_edge_verified",
                     "model_validation_trusted", "allocation_enabled"):
            if report[flag] is not False:
                raise ValueError("research-only flag violated")
        if report["stake"] != 0:
            raise ValueError("nonzero allocation")
        if len(report["source_inventory"]) != 5:
            raise ValueError("incomplete source inventory")
        expected = {"test_matches": 7194, "source_match_rows_eligible": 12123}
        comparisons = {k: {"reference": v, "observed": report[k],
                           "difference": report[k]-v} for k, v in expected.items()}
        metrics = {"global_elo_log_loss": 0.629734,
                   "global_elo_brier": 0.220362,
                   "surface_elo_log_loss": 0.630918,
                   "surface_elo_brier": 0.220550}
        for k, value in metrics.items():
            observed = report["aggregate"][k]
            comparisons[k] = {"reference": value, "observed": observed,
                              "difference": observed-value,
                              "within_rounded_reference_tolerance": abs(observed-value)<=0.000001}
        print(json.dumps({"python":sys.version.split()[0],
                          "replication_comparison":comparisons,
                          "aggregate_report":report}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
