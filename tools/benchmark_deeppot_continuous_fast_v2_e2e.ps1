$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $RepoRoot "src"

$python = $null
try {
    & py -3.11 -c "import sys; print(sys.version)" *> $null
    if ($LASTEXITCODE -eq 0) { $python = @("py", "-3.11") }
} catch {}
if ($null -eq $python) {
    try {
        & python -c "import sys; assert sys.version_info >= (3,11)" *> $null
        if ($LASTEXITCODE -eq 0) { $python = @("python") }
    } catch {}
}
if ($null -eq $python) { throw "Python 3.11+ not found" }

Push-Location $RepoRoot
try {
    if ($python.Count -eq 2) {
        & $python[0] $python[1] ".\tools\benchmark_deeppot_continuous_fast_v2_e2e.py"
    } else {
        & $python[0] ".\tools\benchmark_deeppot_continuous_fast_v2_e2e.py"
    }
    $code = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($code -ne 0) { throw "DeepPot FAST V2 E2E gate exited with code $code" }
