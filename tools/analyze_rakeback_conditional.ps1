param(
    [int]$SamplesPerState = 150,
    [int]$RandomFoldStates = 75,
    [int]$MarginalFoldStates = 75
)

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

$script = Join-Path $PSScriptRoot "analyze_rakeback_conditional.py"
$args = @(
    $script,
    "--training-root", (Join-Path $RepoRoot "runs\continuous_master_fast_v2"),
    "--analysis-csv", (Join-Path $RepoRoot "runs\continuous_master_fast_v2\analysis\V2_2000_to_V2_SEL2500\task_stability.csv"),
    "--samples-per-state", "$SamplesPerState",
    "--random-fold-states", "$RandomFoldStates",
    "--marginal-fold-states", "$MarginalFoldStates",
    "--top-per-n", "3",
    "--n-min", "5",
    "--n-max", "8",
    "--rake", "0.02",
    "--nominal-rb", "0.50",
    "--pvi-factors", "0.60,0.70,0.80"
)

Write-Host "DeepPot CONDITIONAL rakeback sensitivity audit" -ForegroundColor Green
Write-Host "  fixes the zero-eligible coverage problem in the first audit"
Write-Host "  conditions directly on sampled exact infosets from persisted CFR state"
Write-Host "  read-only: no CFR state, RNG or snapshot is modified"
Write-Host ""

Push-Location $RepoRoot
try {
    if ($python.Count -eq 2) { & $python[0] $python[1] @args } else { & $python[0] @args }
    $code = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($code -ne 0) { throw "Conditional rakeback audit exited with code $code" }
