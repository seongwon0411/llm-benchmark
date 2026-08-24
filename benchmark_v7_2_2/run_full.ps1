$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $Utf8NoBom
$OutputEncoding = $Utf8NoBom
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " Local LLM Work Benchmark v7.2.2 - FRESH FULL RUN" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

& .\.venv\Scripts\python.exe -u .\benchmark_v7_2_2.py preflight
if ($LASTEXITCODE -ne 0) { throw "PREFLIGHT FAILED - full run not started." }

New-Item -ItemType Directory -Force .\results\work | Out-Null
Write-Host ""; Write-Host "========== GENERATION: 15 MODELS x 18 TASKS ==========" -ForegroundColor Cyan
& .\.venv\Scripts\python.exe -u .\benchmark_v7_2_2.py run-selected 2>&1 |
    Tee-Object -FilePath ".\results\work\generation.log"
$generationExit = $LASTEXITCODE
if ($generationExit -ne 0) { Write-Warning "Generation process exited with code $generationExit. Inspect generation.log." }

Write-Host ""; Write-Host "========== JUDGE ==========" -ForegroundColor Cyan
& .\.venv\Scripts\python.exe -u .\benchmark_v7_2_2.py judge 2>&1 |
    Tee-Object -FilePath ".\results\work\judge.log"
if ($LASTEXITCODE -ne 0) { throw "Judge phase failed." }

& .\.venv\Scripts\python.exe .\benchmark_v7_2_2.py report
if ($LASTEXITCODE -ne 0) { throw "Report generation failed." }
& .\.venv\Scripts\python.exe .\benchmark_v7_2_2.py finalcheck
if ($LASTEXITCODE -ne 0) { throw "FINALCHECK FAILED - do not use the ranking yet." }
Write-Host ""; Write-Host "FULL RUN COMPLETE" -ForegroundColor Green
Write-Host "Report: $PSScriptRoot\results\work\report.html" -ForegroundColor Green
Start-Process .\results\work\report.html
