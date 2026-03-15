# Bootstrap Paper Agent: create venv, install deps, copy config.
# Run from the repository root: .\scripts\bootstrap.ps1

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
Set-Location $RepoRoot

if (-not (Test-Path "config.example.yaml") -or -not (Test-Path "requirements.txt")) {
    Write-Error "Run this script from the Paper Agent repo root (where config.example.yaml and requirements.txt exist)."
    exit 1
}

Write-Host "Creating virtual environment at .venv ..."
python -m venv .venv

Write-Host "Installing dependencies ..."
& .\.venv\Scripts\pip.exe install -q -r requirements.txt

if (-not (Test-Path "config.yaml")) {
    Copy-Item config.example.yaml config.yaml
    Write-Host "Created config.yaml from config.example.yaml."
} else {
    Write-Host "config.yaml already exists; leaving it unchanged."
}

New-Item -ItemType Directory -Force -Path logs, state | Out-Null

Write-Host ""
Write-Host "Done. Next steps:"
Write-Host "  1. Edit config.yaml (e.g. interests.seeds, delivery.paper_dir)."
Write-Host "  2. If using Raycast: set Config file path and Paper directory in extension Preferences."
Write-Host "  3. Run once: .\.venv\Scripts\python.exe -m paper_agent run --config config.yaml"
Write-Host ""
