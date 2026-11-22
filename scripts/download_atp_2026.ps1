# Windows PowerShell 5.1 — optional personal-research example.
# IMPORTANT: 2026 CSV in this repository is only a historical snapshot,
# possibly incomplete; source has not given us redistribution permission.
# Review repository and data-owner terms before downloading/using.
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path 'data' | Out-Null
$source = 'https://raw.githubusercontent.com/owenparris/tennis/main/2026.csv'
$dest = 'data\ATP_2026.csv'
Write-Host "Downloading historical data from $source ..."
Invoke-WebRequest -Uri $source -OutFile $dest -UseBasicParsing
Get-FileHash -Path $dest -Algorithm SHA256
Write-Host 'The dataset includes historical outcomes and unknown-time odds. RESEARCH ONLY.'
