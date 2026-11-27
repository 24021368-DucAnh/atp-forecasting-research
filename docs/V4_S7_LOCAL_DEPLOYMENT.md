# V4 S7 local Windows deployment

S7 provides a local, read-only dashboard and explicit offline worker commands.
The dashboard binds to `127.0.0.1` only. It does not fetch ATP data, run a
scheduler, fit a model, write forecasts, or activate a candidate while pages
render. Real data stays locked. The synthetic demonstration is fictional and
must be started explicitly.

## Install

Requirements: Windows 10/11, Python 3.11 with the `py` launcher, and package
index access for the initial install. Existing V3 environments are not used.
Open PowerShell in the repository root:

```powershell
.\scripts\windows\atp-lab.ps1 setup
```

Setup creates `.venv-v4` and installs the V4 dashboard/test dependencies from
the hash-checked `requirements/v4-s7.lock`. `uv.lock` records the full
cross-platform project resolution; regenerate exported requirements only
after reviewing the project dependency change. The app and CLI load source
from this checkout through `PYTHONPATH` and do not install or modify a V3
environment.

## Start and stop the dashboard

```powershell
.\scripts\windows\atp-lab.ps1 start
.\scripts\windows\atp-lab.ps1 status
.\scripts\windows\atp-lab.ps1 stop
```

Open `http://127.0.0.1:8501` on the same PC. The server runs in a hidden
window and writes startup output under `%LOCALAPPDATA%\ATP Forecasting Lab`.
Choose **HISTORICAL** to see the hash-verified development evidence. Choose
**SYNTHETIC DEMO** to read local fictional records. Neither mode connects to a
provider. The worker lease is acquired only while an explicit CLI operation
runs; a kernel-managed file lock is released if that process exits or crashes.

## Initialize and seed the synthetic demonstration

```powershell
.\scripts\windows\atp-lab.ps1 demo
```

This explicit action creates the local V5 database when needed and inserts a
small deterministic synthetic history. It is idempotent for a complete demo
and refuses to continue if it finds a partial demo. The Streamlit interface
never initializes or seeds data on its own.

The command-line forms are also available directly:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) "src")
 .\.venv-v4\Scripts\python.exe -m atp_lab.worker.cli init
 .\.venv-v4\Scripts\python.exe -m atp_lab.worker.cli status
 .\.venv-v4\Scripts\python.exe -m atp_lab.worker.cli demo seed
```

## Back up and restore

Backups include a SQLite-consistent database snapshot, every registered
synthetic model artifact, and a SHA-256 inventory. The application never
overwrites an existing backup or restores over an existing data directory.
Restore into a new directory and verify it before changing any local path:

```powershell
.\scripts\windows\atp-lab.ps1 backup -Destination "$env:USERPROFILE\Documents\atp-lab-backup.zip"
.\scripts\windows\atp-lab.ps1 restore -Backup "$env:USERPROFILE\Documents\atp-lab-backup.zip" -Destination "$env:LOCALAPPDATA\ATP Forecasting Lab Restored"
```

Keep backups in a private local location. Do not place the database or model
artifacts in a synced/shared folder. The default local workspace is
`%LOCALAPPDATA%\ATP Forecasting Lab`; set `-DataDirectory` to select another
local folder.

## Checks and manual acceptance

Run the local UI contracts with the installed environment:

```powershell
$env:ATP_LAB_REQUIRE_UI_TESTS = "1"
$env:PYTHONPATH = (Join-Path (Get-Location) "src")
 .\.venv-v4\Scripts\python.exe -m pytest tests/v4/test_dashboard.py -q
```

Run the full core suite in a separate test environment installed from the
matching Windows requirements lock. The V4 dashboard suite is also run by CI
on Windows and Ubuntu.

Before accepting a Windows release, open the rendered dashboard and inspect
all six pages at desktop and narrow-window widths. Check that the navigation
and tables remain readable, historical evidence still shows 7,694 matches
and 18 candidates, the synthetic page shows only local fictional records,
and no page offers refresh, training, or activation. AppTest and CI do not
replace this rendered Windows check. Record the actual browser and Windows
evidence; do not infer it from passing tests.
