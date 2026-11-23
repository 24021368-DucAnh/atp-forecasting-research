"""Reproduce a historical ATP research report using unchanged local inputs.

Windows: .\\.venv\\Scripts\\python.exe scripts\\replay_research.py REPORT.json INPUT.csv
Exit code: 0 = exact reproducible replay; 2 = rejected/non-reproducible.
"""
from __future__ import annotations

import argparse
import json

from atp_gate.research_replay import replay_saved_report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Recheck historical report against source bytes, code, dependencies and model results"
    )
    parser.add_argument("report", help="Previously saved historical JSON report")
    parser.add_argument("sources", nargs="+", help="Original CSV/XLSX paths, in the SAME input order")
    args = parser.parse_args()
    result = replay_saved_report(args.report, args.sources)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] == "REPRODUCED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
