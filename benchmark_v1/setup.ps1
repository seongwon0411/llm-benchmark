$ErrorActionPreference = "Stop"

$HERE = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $HERE

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " Local LLM Benchmark Setup"
Write-Host "==========================================" -ForegroundColor Cyan

# Python launcher
$PY = $null
if (Get-Command py -ErrorAction SilentlyContinue) {
    $PY = "py"
}
elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $PY = "python"
}
else {
    throw "Python을 찾지 못했습니다. Python 3.11+를 설치하세요."
}

if (-not (Get-Command lms -ErrorAction SilentlyContinue)) {
    Write-Host "WARNING: lms 명령이 PATH에 없습니다." -ForegroundColor Yellow
    Write-Host "LM Studio를 실행한 뒤 lms --help가 작동하는지 확인하세요."
}

if (-not (Test-Path ".venv")) {
    if ($PY -eq "py") {
        py -3 -m venv .venv
    }
    else {
        python -m venv .venv
    }
}

& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt

Write-Host "Checking benchmark.py syntax..." -ForegroundColor Cyan
& ".\.venv\Scripts\python.exe" -m py_compile .\benchmark.py
if ($LASTEXITCODE -ne 0) { throw "benchmark.py syntax check failed" }

New-Item -ItemType Directory -Force "C:\AI\Benchmark\results" | Out-Null

Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host ""
Write-Host "1) Inventory:"
Write-Host '   .\.venv\Scripts\python.exe .\benchmark.py inventory --mode standard'
Write-Host ""
Write-Host "2) 1-model smoke benchmark:"
Write-Host '   .\.venv\Scripts\python.exe .\benchmark.py run --mode quick --max-models 1'
Write-Host ""
Write-Host "3) Full standard benchmark:"
Write-Host '   .\.venv\Scripts\python.exe .\benchmark.py run --mode standard'
