# Reproducible local Elo skill study. No network, raw CSV upload or bets.
$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonExe = Join-Path $repo ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Local Python virtual environment missing: $pythonExe"
}

$snapshots = @()
foreach ($season in 2021..2025) {
    $folder = Join-Path $repo ("data\tml\{0}" -f $season)
    $manifest = Join-Path $folder "index.json"
    if (-not (Test-Path $manifest)) {
        throw "Missing immutable local TML season $season. Run tml-update --year $season first."
    }
    $metadata = Get-Content -Path $manifest -Raw | ConvertFrom-Json
    if ($metadata.year -ne $season -or [string]::IsNullOrWhiteSpace($metadata.snapshot_filename)) {
        throw "Source manifest has invalid season identity: $manifest"
    }
    $snapshot = Join-Path $folder $metadata.snapshot_filename
    if (-not (Test-Path $snapshot)) {
        throw "Missing historical source bytes for year $season: $snapshot"
    }
    $snapshots += $snapshot
}

$reportDir = Join-Path $repo "reports\elo"
New-Item -ItemType Directory -Path $reportDir -Force | Out-Null
$output = Join-Path $reportDir "tml_2021_2025_skill.json"
Push-Location $repo
try {
    & $pythonExe -m atp_gate tml-elo-experiment @snapshots --out $output
    if ($LASTEXITCODE -ne 0) {
        throw "Noncommercial Elo study failed; source files were not modified."
    }
    Write-Host "Research-only aggregate report: $output"
}
finally {
    Pop-Location
}
