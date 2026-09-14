param(
    [string]$TrainingRoot = "C:\DeepPot\runs\continuous_master_fast_v2",
    [int]$TasksPerN = 4,
    [int]$SamplesPerTask = 1500,
    [int]$Seed = 9143500
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $RepoRoot "src"
$Python = "py"
$PythonArgs = @("-3.11")

Write-Host "DeepPot SEL3500 MIXED x GREEDY x HYBRID robustness gate"
Write-Host "  fixed/non-adaptive opponent families"
Write-Host "  finite protocol: 4 canonical flops per N, 1500 common-random deals/task by default"
Write-Host "  read-only: no CFR state, RNG, snapshot, DLL or formula is modified"

& $Python @PythonArgs (Join-Path $PSScriptRoot "analyze_policy_robustness_SEL3500.py") `
    --training-root $TrainingRoot `
    --tasks-per-n $TasksPerN `
    --samples-per-task $SamplesPerTask `
    --seed $Seed

$code = $LASTEXITCODE
if ($code -ne 0) {
    throw "SEL3500 base-policy robustness gate exited with code $code"
}
