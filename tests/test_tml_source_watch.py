"""Guard rail: known provider row anomalies should not stop the daily metadata watch.

The downloader must keep anomalous rows quarantined and record their counts,
while a malformed/unsafe whole-source read must still cause a hard failure.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_tml_watch_reports_quarantined_rows_without_aborting_on_known_anomalies():
    workflow = (ROOT / ".github/workflows/tml-source-watch.yml").read_text(encoding="utf-8")
    assert "SOURCE QUARANTINE:" in workflow
    assert "UNIDENTIFIABLE_ROWS_REVIEW_REQUIRED" in workflow
    assert "raise SystemExit(\"Official source has unidentifiable/malformed records" not in workflow
    # Critical February 2024 candidate event/round inconsistencies still fail.
    assert 'if result["anomalies"]:' in workflow
    assert "manual review required" in workflow
