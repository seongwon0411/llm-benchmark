$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $Utf8NoBom
$OutputEncoding = $Utf8NoBom
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"


Write-Host "Local LLM Work Benchmark v7.2.2 setup" -ForegroundColor Cyan

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    py -3 -m venv .venv
}

.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt

Write-Host "" 
Write-Host "Running deterministic selftest..." -ForegroundColor Cyan
.\.venv\Scripts\python.exe -u .\benchmark_v7_2_2.py selftest
if ($LASTEXITCODE -ne 0) { throw "SELFTEST FAILED" }

Write-Host "" 
Write-Host "Setup complete: v7.2.2" -ForegroundColor Green
Write-Host "Before the full run, keep LM Studio Require Authentication ON and set LM_API_TOKEN in this PowerShell session." -ForegroundColor Yellow
Write-Host 'Then run: .\run_full.ps1' -ForegroundColor Cyan
