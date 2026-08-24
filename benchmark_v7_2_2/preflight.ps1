$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $Utf8NoBom
$OutputEncoding = $Utf8NoBom
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

& .\.venv\Scripts\python.exe -u .\benchmark_v7_2_2.py preflight
exit $LASTEXITCODE
