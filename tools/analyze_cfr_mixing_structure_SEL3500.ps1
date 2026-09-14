param()

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

$script = Join-Path $PSScriptRoot "analyze_cfr_mixing_structure_SEL3500.py"
$args = @(
    $script,
    "--training-root", (Join-Path $RepoRoot "runs\continuous_master_fast_v2")
)

Write-Host "DeepPot SEL3500 CFR mixing-structure audit" -ForegroundColor Green
Write-Host "  full read-only scan of persisted CFR state"
Write-Host "  compares cumulative average CFR policy to final current regret-matching policy"
Write-Host "  separates last actor from earlier actors"
Write-Host "  no CFR state, RNG, snapshot, DLL or formula is modified"
Write-Host ""

Push-Location $RepoRoot
try {
    if ($python.Count -eq 2) { & $python[0] $python[1] @args } else { & $python[0] @args }
    $code = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($code -ne 0) { throw "SEL3500 CFR mixing audit exited with code $code" }
