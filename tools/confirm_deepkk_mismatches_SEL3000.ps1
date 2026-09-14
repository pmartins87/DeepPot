param(
    [int]$SamplesPerState = 5000,
    [double]$MinEffectiveVisits = 100.0,
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

$script = Join-Path $PSScriptRoot "confirm_deepkk_mismatches_SEL3000.py"
$args = @(
    $script,
    "--training-root", (Join-Path $RepoRoot "runs\continuous_master_fast_v2"),
    "--gate-json", (Join-Path $RepoRoot "runs\continuous_master_fast_v2\analysis\deepkk_final_gate_SEL3000\deepkk_final_gate.json"),
    "--samples-per-state", "$SamplesPerState",
    "--min-effective-visits", "$MinEffectiveVisits",
    "--rake", "0.02",
    "--cashback-per-contribution", "$CashbackPerContribution"
)

Write-Host "DeepPot high-sample confirmation of SEL3000 EV mismatches" -ForegroundColor Green
Write-Host "  rechecks only states flagged by the prior final gate"
Write-Host "  default: 5,000 conditional samples per target state"
Write-Host "  observed cashback is passed directly as cashback/contribution"
Write-Host "  read-only: no CFR state, RNG, snapshot, DLL or formula is modified"
Write-Host ""

Push-Location $RepoRoot
try {
    if ($python.Count -eq 2) { & $python[0] $python[1] @args } else { & $python[0] @args }
    $code = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($code -ne 0) { throw "SEL3000 mismatch confirmation exited with code $code" }
