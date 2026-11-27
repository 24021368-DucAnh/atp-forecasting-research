param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet("setup", "start", "stop", "status", "demo", "backup", "restore")]
    [string]$Action,
    [string]$Destination,
    [string]$Backup,
    [string]$DataDirectory = (Join-Path $env:LOCALAPPDATA "ATP Forecasting Lab"),
    [int]$Port = 8501
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Venv = Join-Path $Root ".venv-v4"
$Python = Join-Path $Venv "Scripts\python.exe"
$PidFile = Join-Path $DataDirectory "dashboard.pid"
$StdoutLog = Join-Path $DataDirectory "dashboard.stdout.log"
$StderrLog = Join-Path $DataDirectory "dashboard.stderr.log"

function Invoke-LocalPython([string[]]$Arguments) {
    $env:ATP_LAB_DATA_DIR = $DataDirectory
    $env:PYTHONPATH = Join-Path $Root "src"
    Push-Location $Root
    try {
        & $Python @Arguments
        if ($LASTEXITCODE -ne 0) { throw "ATP Forecasting Lab command failed with exit code $LASTEXITCODE." }
    }
    finally { Pop-Location }
}

switch ($Action) {
    "setup" {
        if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
            throw "Install Python 3.11 for Windows, then run this setup action again."
        }
        & py -3.11 --version
        if ($LASTEXITCODE -ne 0) { throw "Python 3.11 was not found. Install it before setup." }
        if (-not (Test-Path $Python)) {
            Push-Location $Root
            try { & py -3.11 -m venv $Venv; if ($LASTEXITCODE -ne 0) { throw "Could not create the V4 environment." } }
            finally { Pop-Location }
        }
        & $Python -m pip install --require-hashes -r (Join-Path $Root "requirements\v4-s7.lock")
        if ($LASTEXITCODE -ne 0) { throw "Pinned V4 dependencies could not be installed." }
        & $Python -m pip check
        if ($LASTEXITCODE -ne 0) { throw "The V4 environment has dependency conflicts." }
        Write-Output "V4 environment ready at $Venv"
    }
    "start" {
        if (-not (Test-Path $Python)) { throw "Run the setup action first." }
        if ($Port -lt 1024 -or $Port -gt 65535) { throw "Choose a local port between 1024 and 65535." }
        $app = Join-Path $Root "dashboard\app.py"
        $existingListener = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
        if ($existingListener.Count -gt 0) { throw "Local port $Port is already in use. No dashboard process was started." }
        New-Item -ItemType Directory -Force -Path $DataDirectory | Out-Null
        if (Test-Path $PidFile) {
            try { $oldRecord = Get-Content -Raw $PidFile | ConvertFrom-Json -ErrorAction Stop }
            catch { throw "The dashboard process record is invalid; inspect it before starting another." }
            $oldIds = @([int]$oldRecord.server_pid, [int]$oldRecord.launcher_pid) | Select-Object -Unique
            foreach ($oldId in $oldIds) {
                $oldProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $oldId" -ErrorAction SilentlyContinue
                if ($oldProcess -and $oldProcess.CommandLine -like "*$app*") {
                    throw "A dashboard process is already recorded. Check status before starting another."
                }
            }
            Remove-Item -LiteralPath $PidFile
        }
        $env:ATP_LAB_DATA_DIR = $DataDirectory
        $env:PYTHONPATH = Join-Path $Root "src"
        $args = @("-m", "streamlit", "run", "`"$app`"", "--server.address", "127.0.0.1",
                  "--server.port", "$Port", "--server.headless", "true",
                  "--browser.gatherUsageStats", "false")
        $process = Start-Process -FilePath $Python -ArgumentList $args -WorkingDirectory $Root `
            -WindowStyle Hidden -PassThru -RedirectStandardOutput $StdoutLog -RedirectStandardError $StderrLog
        $started = $false
        for ($attempt = 0; $attempt -lt 40; $attempt++) {
            $process.Refresh()
            if ($process.HasExited) { break }
            $listeners = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
            if ($listeners.Count -gt 0) {
                $response = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/_stcore/health" -TimeoutSec 2 `
                    -UseBasicParsing -ErrorAction SilentlyContinue
                if ($response.StatusCode -eq 200) {
                    $serverPid = [int]$listeners[0].OwningProcess
                    $serverInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $serverPid" -ErrorAction SilentlyContinue
                    if ($serverInfo -and $serverInfo.CommandLine -like "*$app*" `
                            -and $serverInfo.CommandLine -like "*--server.port $Port*") {
                        $started = $true
                        break
                    }
                }
            }
            Start-Sleep -Milliseconds 250
        }
        if (-not $started) {
            if (-not $process.HasExited) { Stop-Process -Id $process.Id -ErrorAction SilentlyContinue }
            Remove-Item -LiteralPath $PidFile -ErrorAction SilentlyContinue
            Get-Content $StderrLog -ErrorAction SilentlyContinue
            throw "Dashboard did not bind its local port. Review $StderrLog."
        }
        @{ launcher_pid = $process.Id; server_pid = $serverPid; port = $Port } |
            ConvertTo-Json -Compress | Set-Content -Path $PidFile -Encoding ascii
        Write-Output "Dashboard started at http://127.0.0.1:$Port (PID $($process.Id))."
    }
    "stop" {
        if (-not (Test-Path $PidFile)) { Write-Output "Dashboard is stopped."; break }
        try { $record = Get-Content -Raw $PidFile | ConvertFrom-Json -ErrorAction Stop }
        catch { throw "The dashboard process record is invalid; no process was stopped." }
        $expectedApp = Join-Path $Root "dashboard\app.py"
        $ids = @([int]$record.server_pid, [int]$record.launcher_pid) | Select-Object -Unique
        $processes = @($ids | ForEach-Object {
            Get-CimInstance Win32_Process -Filter "ProcessId = $_" -ErrorAction SilentlyContinue
        } | Where-Object { $_ })
        foreach ($processInfo in $processes) {
            if ($processInfo.CommandLine -notlike "*$expectedApp*" `
                    -or $processInfo.CommandLine -notlike "*--server.port $($record.port)*") {
                throw "A recorded process does not match this dashboard. No process was stopped."
            }
        }
        if ($processes.Count -eq 0) {
            Remove-Item -LiteralPath $PidFile
            Write-Output "Dashboard was already stopped; its stale process record was cleared."
            break
        }
        foreach ($processInfo in ($processes | Sort-Object { if ($_.ProcessId -eq $record.server_pid) { 0 } else { 1 } })) {
            Stop-Process -Id $processInfo.ProcessId -ErrorAction SilentlyContinue
        }
        Remove-Item -LiteralPath $PidFile
        Write-Output "Dashboard stopped."
    }
    "status" {
        if (Test-Path $Python) {
            Invoke-LocalPython @("-m", "atp_lab.worker.cli", "status", "--data-dir", $DataDirectory)
        }
        else { Write-Output "V4 environment is not installed." }
        if (Test-Path $PidFile) {
            try { $record = Get-Content -Raw $PidFile | ConvertFrom-Json -ErrorAction Stop }
            catch { throw "The dashboard process record is invalid." }
            $expectedApp = Join-Path $Root "dashboard\app.py"
            $serverInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $([int]$record.server_pid)" -ErrorAction SilentlyContinue
            if ($serverInfo -and $serverInfo.CommandLine -like "*$expectedApp*" `
                    -and $serverInfo.CommandLine -like "*--server.port $([int]$record.port)*") {
                Write-Output "Dashboard process: RUNNING (PID $($record.server_pid), port $($record.port))"
            }
            else { Write-Output "Dashboard process: STOPPED (stale PID record)" }
        }
        else { Write-Output "Dashboard process: STOPPED" }
    }
    "demo" {
        if (-not (Test-Path $Python)) { throw "Run the setup action first." }
        New-Item -ItemType Directory -Force -Path $DataDirectory | Out-Null
        if (-not (Test-Path (Join-Path $DataDirectory "atp_lab.sqlite"))) {
            Invoke-LocalPython @("-m", "atp_lab.worker.cli", "init", "--data-dir", $DataDirectory)
        }
        Invoke-LocalPython @("-m", "atp_lab.worker.cli", "demo", "seed", "--data-dir", $DataDirectory)
    }
    "backup" {
        if (-not $Destination) { throw "Provide -Destination with a new backup file path." }
        Invoke-LocalPython @("-m", "atp_lab.worker.cli", "backup", "--data-dir", $DataDirectory, "--destination", $Destination)
    }
    "restore" {
        if (-not $Destination -or -not $Backup) { throw "Provide -Backup and a new -Destination data directory." }
        New-Item -ItemType Directory -Force -Path $DataDirectory | Out-Null
        Invoke-LocalPython @("-m", "atp_lab.worker.cli", "restore", "--data-dir", $DataDirectory, "--backup", $Backup, "--destination", $Destination)
    }
}
