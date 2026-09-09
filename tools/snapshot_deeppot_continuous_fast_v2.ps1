param(
    [Parameter(Mandatory=$true)][string]$Name,
    [string]$RuntimeIndex = "",
    [string]$StayAction = "BetMax",
    [switch]$DisableLive
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$TrainingRoot = Join-Path $RepoRoot "runs\continuous_master_fast_v2"
if ([string]::IsNullOrWhiteSpace($RuntimeIndex)) {
    $RuntimeIndex = Join-Path $RepoRoot "runs\deeppot_runtime\deeppot_runtime_index.bin"
}

$manifestPath = Join-Path $TrainingRoot "CONTINUOUS_MANIFEST.json"
if (-not (Test-Path $manifestPath)) { throw "Fast-V2 continuous manifest not found: $manifestPath" }
$manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
if ($manifest.stage -notin @("paused", "completed")) {
    throw "Training must be safely PAUSED or COMPLETED before snapshot. Current stage: $($manifest.stage)"
}
if (-not (Test-Path $RuntimeIndex)) { throw "Runtime index not found: $RuntimeIndex" }

$env:PYTHONPATH = Join-Path $RepoRoot "src"
$args = @(
    "-m", "deeppot.continuous_snapshot",
    "--training-root", $TrainingRoot,
    "--name", $Name,
    "--runtime-index", $RuntimeIndex,
    "--stay-action", $StayAction
)
if ($DisableLive) { $args += "--disable-live" }

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

Write-Host "DeepPot FAST V2 continuous snapshot" -ForegroundColor Green
Write-Host "  name: $Name"
Write-Host "  training root: $TrainingRoot"
Write-Host "  stage: $($manifest.stage)"
Write-Host "  weighted mean visits: $($manifest.weighted_mean_training_visits)"
Write-Host "  STAY transport: $StayAction"
Write-Host "  v5-ready DeepPot.txt will be emitted unless -DisableLive is used."
Write-Host "  training state will NOT be consumed or reset."

Push-Location $RepoRoot
try {
    if ($python.Count -eq 2) { & $python[0] $python[1] @args } else { & $python[0] @args }
    $code = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($code -ne 0) { throw "DeepPot FAST V2 snapshot exporter exited with code $code" }
