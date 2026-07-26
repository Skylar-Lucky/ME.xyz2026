param([int]$Port = 8010)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $python)) {
    throw "Virtual env missing. Run first: py -3.12 -m venv .venv"
}

Set-Location (Join-Path $projectRoot 'backend')
Write-Host "ME.xyz running: http://127.0.0.1:$Port"
Write-Host "Press Ctrl+C to stop."
& $python -m uvicorn main:app --host 127.0.0.1 --port $Port
