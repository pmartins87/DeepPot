param(
    [Parameter(Mandatory=$true)][string]$Name,
    [string]$TrainingRoot = "",
    [string]$RuntimeIndex = "",
    [string]$StayAction = "BetPot",
    [switch]$DisableLive
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($TrainingRoot)) {
    $TrainingRoot = Join-Path $RepoRoot "runs\continuous_master"
}
if ([string]::IsNullOrWhiteSpace($RuntimeIndex)) {
    $RuntimeIndex = Join-Path $RepoRoot "runs\deeppot_runtime\deeppot_runtime_index.bin"
}

$manifestPath = Join-Path $TrainingRoot "CONTINUOUS_MANIFEST.json"
if (-not (Test-Path $manifestPath)) { throw "Continuous manifest not found: $manifestPath" }
$manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
if ($manifest.stage -notin @("paused", "completed")) {
    throw "Training must be safely PAUSED or COMPLETED before snapshot. Current stage: $($manifest.stage)"
}
if (-not (Test-Path $RuntimeIndex)) { throw "Runtime index not found: $RuntimeIndex" }

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

Write-Host "DeepPot continuous snapshot" -ForegroundColor Green
Write-Host "  name: $Name"
Write-Host "  training root: $TrainingRoot"
Write-Host "  training stage: $($manifest.stage)"
Write-Host "  current weighted mean visits: $($manifest.weighted_mean_training_visits)"
Write-Host "  current task-min median: $($manifest.task_min_visit_median)"
Write-Host "  training state will NOT be consumed or reset."

$env:PYTHONPATH = Join-Path $RepoRoot "src"
$args = @(
    "-m", "deeppot.continuous_snapshot",
    "--training-root", $TrainingRoot,
    "--name", $Name,
    "--runtime-index", $RuntimeIndex,
    "--stay-action", $StayAction
)
if ($DisableLive) { $args += "--disable-live" }

Push-Location $RepoRoot
try {
    if ($python.Count -eq 2) { & $python[0] $python[1] @args } else { & $python[0] @args }
    $code = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($code -ne 0) { throw "DeepPot snapshot exporter exited with code $code" }
