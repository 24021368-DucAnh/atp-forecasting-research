# V4 S1 local dashboard (offline preview)

This is a historical evidence viewer, not a live match forecasting service.
No ingestion, scheduler, model fitting, model artifacts, SQLite or network
provider access is implemented in S1. The six navigation pages explicitly
identify unavailable operational data. Only Overview shows real historical
aggregate metrics. The exact P2.4 evidence must pass SHA-256 verification.

From a clean Git checkout of the reviewed V4 branch, in PowerShell at the
repository root, use a separate Python 3.11 virtual environment. Do not
replace the V3 environment. Installation requires package-index access;
running the app does not require a sports data source.

    py -3.11 -m venv .venv-v4
    .\.venv-v4\Scripts\python.exe -m pip install -r requirements/v4-ui.txt -e .
    .\.venv-v4\Scripts\python.exe -m pip check
    $env:ATP_LAB_REQUIRE_UI_TESTS = "1"
    .\.venv-v4\Scripts\python.exe -m pytest tests/v4/test_dashboard.py -q
    .\.venv-v4\Scripts\python.exe -m streamlit run dashboard/app.py --server.address 127.0.0.1 --server.port 8501 --browser.gatherUsageStats false

Open http://127.0.0.1:8501 on the same PC. Ctrl+C stops the server. Do not
expose it on the LAN or internet. Do not commit the virtual environment.
Use a local ignored environment outside the repository if necessary.

Manual acceptance: Overview shows 7,694 matches, 18 historical candidates,
LOCKED real data and Unavailable new predictions; filter by global_elo;
inspect all five remaining pages for honest locked states; check keyboard
navigation, readable table and chart, desktop and narrow window layout.
No source URL or provider connection is necessary. AppTest is not visual
or accessibility certification. Record actual Windows/browser smoke
evidence before final S1 acceptance. Direct dependency pins are not a
complete transitive lock; full local deployment locks belong to S7.
