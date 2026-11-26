# One-shot run on Windows (PowerShell): starts Oracle 23ai Free, loads data, runs the benchmark, builds the charts.
# Requirements: Docker Desktop (or Podman with docker compose) and Python 3.10+ on PATH.
# Usage, from the repository root:  powershell -ExecutionPolicy Bypass -File scripts\run.ps1
$ErrorActionPreference = "Stop"

docker compose up -d
Write-Host "Waiting for Oracle to be healthy (first start: 1-2 minutes)..."
$container = (docker compose ps -q oracle).Trim()
do {
    Start-Sleep -Seconds 5
    $status = (docker inspect --format "{{.State.Health.Status}}" $container).Trim()
    Write-Host "  status: $status"
} until ($status -eq "healthy")

if (-not (Test-Path .venv)) { python -m venv .venv }
.\.venv\Scripts\python -m pip install --quiet -r bench\requirements.txt
.\.venv\Scripts\python bench\bench.py --setup --system-password ChangeMe_123
.\.venv\Scripts\python bench\charts.py

Write-Host "Done. Results in results\ and the cover image in docs\cover.png"
