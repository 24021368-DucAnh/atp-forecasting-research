# Personal/noncommercial TML ATP season refresh, owner-invoked or scheduled locally.
# No model training, no bookmaker access, no raw CSV upload.
param([int]$Season = (Get-Date).Year)

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonExe = Join-Path $repo ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Create the local .venv and install the atp_gate package before scheduling."
}
$privateRoot = Join-Path $repo "data\tml"
$reportDir = Join-Path $repo "reports\tml_updates"
New-Item -ItemType Directory -Path $reportDir -Force | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"

Push-Location $repo
try {
    foreach ($year in @(2024, $Season) | Select-Object -Unique) {
        $reportPath = Join-Path $reportDir ("{0}-{1}.json" -f $year, $stamp)
        & $pythonExe -m atp_gate tml-update --year $year --root $privateRoot |
            Set-Content -Path $reportPath -Encoding utf8
        if ($LASTEXITCODE -ne 0) {
            throw "TML update for $year failed. Inspect report: $reportPath"
        }
        Write-Host "TML research source update metadata: $reportPath"
    }
}
finally {
    Pop-Location
}
