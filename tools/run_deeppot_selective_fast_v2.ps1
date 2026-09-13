param(
    [double]$ChangedPctThreshold = 2.0,
    [int]$TargetMinVisits = 2500,
    [int]$ChunkIterations = 50000,
    [int]$Workers = 31,
    [double]$MaxWallHours = 0
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$TrainingRoot = Join-Path $RepoRoot "runs\continuous_master_fast_v2"
$AnalysisCsv = Join-Path $TrainingRoot "analysis\V2_1500_to_V2_2000\task_stability.csv"

if (-not (Test-Path $AnalysisCsv)) {
    throw "Selective analysis CSV not found: $AnalysisCsv"
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

Write-Host "DeepPot FAST V2 selective continuation" -ForegroundColor Green
Write-Host "  selection source: V2_1500 -> V2_2000 per-task stability"
Write-Host "  rule: changed_pct > $ChangedPctThreshold"
Write-Host "  target for selected tasks: visit_min >= $TargetMinVisits"
Write-Host "  non-selected tasks remain frozen at their current CFR state"
Write-Host "  mathematical/source-locked files are NOT changed by this launcher"
Write-Host ""
Write-Host "INTERRUPTION:" -ForegroundColor Yellow
Write-Host "  Press Ctrl+C once. New chunks stop; active chunks finish/checkpoint."
Write-Host "  Wait for 'SAFE TO CLOSE' before closing PowerShell."
Write-Host "  Rerun THIS SAME COMMAND to resume the selective continuation."
Write-Host ""

$env:PYTHONPATH = Join-Path $RepoRoot "src"
$args = @(
    (Join-Path $RepoRoot "tools\run_deeppot_selective_fast_v2.py"),
    "--training-root", $TrainingRoot,
    "--analysis-csv", $AnalysisCsv,
    "--changed-pct-threshold", "$ChangedPctThreshold",
    "--target-min-visits", "$TargetMinVisits",
    "--chunk-iterations", "$ChunkIterations",
    "--workers", "$Workers",
    "--seed", "123",
    "--rake", "0.02",
    "--max-wall-hours", "$MaxWallHours"
)

Push-Location $RepoRoot
try {
    if ($python.Count -eq 2) { & $python[0] $python[1] @args } else { & $python[0] @args }
    $code = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($code -ne 0) { throw "DeepPot selective continuation exited with code $code" }
