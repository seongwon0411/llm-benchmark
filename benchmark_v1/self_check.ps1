Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)

$PY = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $PY)) {
    throw ".venv Python이 없습니다. 먼저 .\setup.ps1 을 실행하세요."
}

Write-Host "[1/4] Python syntax check..." -ForegroundColor Cyan
& $PY -m py_compile .\benchmark.py .\scorer_self_test.py
if ($LASTEXITCODE -ne 0) { throw "Python syntax check failed" }

Write-Host "[2/4] JSON check..." -ForegroundColor Cyan
& $PY -c "import json; json.load(open('config.json',encoding='utf-8')); json.load(open('tasks.json',encoding='utf-8')); print('JSON OK')"
if ($LASTEXITCODE -ne 0) { throw "JSON check failed" }

Write-Host "[3/4] Scorer regression tests..." -ForegroundColor Cyan
& $PY .\scorer_self_test.py
if ($LASTEXITCODE -ne 0) { throw "Scorer regression test failed" }

Write-Host "[4/4] CLI check..." -ForegroundColor Cyan
& $PY .\benchmark.py --help | Out-Null
if ($LASTEXITCODE -ne 0) { throw "CLI check failed" }

Write-Host "SELF CHECK PASSED" -ForegroundColor Green
