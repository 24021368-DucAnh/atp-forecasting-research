"""Offline UI contract; run in the separate V4 Streamlit environment."""
import os
from pathlib import Path

import pytest

if os.environ.get("ATP_LAB_REQUIRE_UI_TESTS") == "1":
    from streamlit.testing.v1 import AppTest
else:
    AppTest = pytest.importorskip("streamlit.testing.v1").AppTest

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "dashboard" / "app.py"
EVIDENCE = ROOT / "docs/research/p2_4_fixed_ablation_evidence_20261125.json"


def run_app(path=APP):
    assert path.is_file(), "S1 offline dashboard entrypoint not implemented"
    at = AppTest.from_file(str(path), default_timeout=20).run()
    assert not at.exception
    return at


def test_overview_shows_verified_historical_only():
    at = run_app()
    assert at.title[0].value == "ATP Forecasting Lab"
    assert any("HISTORICAL DEVELOPMENT ONLY" in c.value for c in at.caption)
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Historical matches"] == "7,694"
    assert metrics["Historical candidates"] == "18"
    assert metrics["Real data"] == "LOCKED"
    assert metrics["New predictions"] == "Unavailable"
    table = at.dataframe[0].value
    assert len(table) == 18
    row = table.loc[table["Model"] == "logistic_platt"].iloc[0]
    assert row["Accuracy (%)"] == pytest.approx(4970 / 7694 * 100)
    assert row["Log loss"] == pytest.approx(0.6213113231986881)
    assert row["Brier"] == pytest.approx(0.21651241501108331)
    assert row["Coverage (%)"] == 100


def test_historical_model_filter_is_read_only():
    at = run_app()
    at.multiselect[0].set_value(["global_elo"]).run()
    assert not at.exception
    assert at.dataframe[0].value["Model"].tolist() == ["global_elo"]
    assert not at.button


@pytest.mark.parametrize("page", [
    "Upcoming", "Tournaments", "Results", "Model Lab", "Data Health",
])
def test_locked_pages_do_not_invent_live_data(page):
    at = run_app()
    at.sidebar.radio[0].set_value(page).run()
    assert not at.exception
    assert any(h.value == page for h in at.header)
    assert any("LOCKED" in item.value for item in at.info)
    assert not at.button
    assert not at.dataframe


@pytest.mark.parametrize("tampered", [False, True])
def test_missing_or_altered_evidence_is_visible_without_metrics(tmp_path, tampered):
    assert APP.is_file(), "S1 offline dashboard entrypoint not implemented"
    local_app = tmp_path / "dashboard" / "app.py"
    local_app.parent.mkdir()
    local_app.write_bytes(APP.read_bytes())
    if tampered:
        evidence = tmp_path / EVIDENCE.relative_to(ROOT)
        evidence.parent.mkdir(parents=True)
        evidence.write_bytes(EVIDENCE.read_bytes() + b" ")
    at = run_app(local_app)
    assert any("Historical evidence unavailable or invalid" in e.value
               for e in at.error)
    assert not at.metric
    assert not at.dataframe
