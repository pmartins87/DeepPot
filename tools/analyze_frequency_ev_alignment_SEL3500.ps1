param(
    [int]$TasksPerN = 2,
    [int]$StatesPerStratum = 3,
    [int]$SamplesPerState = 1000,
    [double]$MinEffectiveVisits = 50.0,
    [double]$CashbackPerContribution = 0.007
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

$script = Join-Path $PSScriptRoot "analyze_frequency_ev_alignment_SEL3500.py"
$args = @(
    $script,
    "--training-root", (Join-Path $RepoRoot "runs\continuous_master_fast_v2"),
    "--tasks-per-n", "$TasksPerN",
    "--states-per-stratum", "$StatesPerStratum",
    "--samples-per-state", "$SamplesPerState",
    "--min-effective-visits", "$MinEffectiveVisits",
    "--rake", "0.02",
    "--cashback-per-contribution", "$CashbackPerContribution"
)

Write-Host "DeepPot SEL3500 CFR-frequency vs conditional-EV alignment audit" -ForegroundColor Green
Write-Host "  tests whether stronger CFR majority frequency predicts the EV-best pure action"
Write-Host "  stratified by majority probability and earlier-vs-last actor"
Write-Host "  compares greedy-pure EV to mixed-CFR EV against fixed SEL3500 CFR opponents"
Write-Host "  includes observed cashback sensitivity"
Write-Host "  read-only: no CFR state, RNG, snapshot, DLL or formula is modified"
Write-Host ""

Push-Location $RepoRoot
try {
    if ($python.Count -eq 2) { & $python[0] $python[1] @args } else { & $python[0] @args }
    $code = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($code -ne 0) { throw "SEL3500 frequency-vs-EV audit exited with code $code" }
