param(
    [string]$Previous = "V2_1500",
    [string]$Current = "V2_2000",
    [string]$TrainingRoot = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($TrainingRoot)) {
    $TrainingRoot = Join-Path $RepoRoot "runs\continuous_master_fast_v2"
}

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

$env:PYTHONPATH = Join-Path $RepoRoot "src"
$script = Join-Path $PSScriptRoot "analyze_deeppot_selective_gate.py"
$args = @(
    $script,
    "--training-root", $TrainingRoot,
    "--previous", $Previous,
    "--current", $Current
)

Write-Host "DeepPot selective-training stability gate" -ForegroundColor Green
Write-Host "  previous: $Previous"
Write-Host "  current:  $Current"
Write-Host "  training root: $TrainingRoot"
Write-Host "  read-only: no CFR state, RNG, summaries or snapshots will be modified"
Write-Host ""

Push-Location $RepoRoot
try {
    if ($python.Count -eq 2) { & $python[0] $python[1] @args } else { & $python[0] @args }
    $code = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($code -ne 0) { throw "DeepPot selective stability analyzer exited with code $code" }
