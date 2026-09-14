param(
    [int]$SamplesPerState = 500,
    [int]$MarginalStates = 50,
    [int]$RandomStates = 25
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

$script = Join-Path $PSScriptRoot "analyze_deepkk_final_gate_conditional.py"
$args = @(
    $script,
    "--training-root", (Join-Path $RepoRoot "runs\continuous_master_fast_v2"),
    "--analysis-csv", (Join-Path $RepoRoot "runs\continuous_master_fast_v2\analysis\V2_SEL2500_to_V2_SEL3000\task_stability.csv"),
    "--samples-per-state", "$SamplesPerState",
    "--marginal-states", "$MarginalStates",
    "--random-states", "$RandomStates",
    "--top-per-n", "3",
    "--n-min", "5",
    "--n-max", "8",
    "--rake", "0.02",
    "--nominal-rb", "0.50",
    "--pvi-factors", "0.60,0.70,0.80"
)

Write-Host "DeepPot conditional DeepKK-style final EV/CI gate" -ForegroundColor Green
Write-Host "  uses persisted average CFR policy from SEL3000"
Write-Host "  audits both marginal and broad states"
Write-Host "  reports confident EV-best vs solver-greedy mismatches"
Write-Host "  includes empirical rebate sensitivity without changing CFR economics"
Write-Host "  read-only: no CFR state, RNG or snapshot is modified"
Write-Host ""

Push-Location $RepoRoot
try {
    if ($python.Count -eq 2) { & $python[0] $python[1] @args } else { & $python[0] @args }
    $code = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($code -ne 0) { throw "DeepKK-style final gate exited with code $code" }
