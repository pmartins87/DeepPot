param(
    [string]$TrainingRoot = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($TrainingRoot)) {
    $TrainingRoot = Join-Path $RepoRoot "runs\continuous_master"
}
$manifestPath = Join-Path $TrainingRoot "CONTINUOUS_MANIFEST.json"
if (-not (Test-Path $manifestPath)) { throw "Continuous manifest not found: $manifestPath" }
$m = Get-Content $manifestPath -Raw | ConvertFrom-Json

Write-Host ""
Write-Host "DEEPPOT CONTINUOUS TRAINING STATUS" -ForegroundColor Green
Write-Host "  stage: $($m.stage)"
Write-Host "  target min visits / exact infoset: $($m.target_min_visits_per_infoset)"
Write-Host "  tasks checkpointed: $($m.tasks_with_state) / $($m.tasks_total)"
Write-Host "  tasks already at target: $($m.tasks_target_reached) / $($m.tasks_total)"
Write-Host ("  weighted mean visits: {0:N2}" -f [double]$m.weighted_mean_training_visits)
Write-Host "  global task minimum: $($m.task_min_visit_global)"
Write-Host "  median of per-task minima: $($m.task_min_visit_median)"
Write-Host "  iterations/task min | median | max: $($m.iterations_completed_min) | $($m.iterations_completed_median) | $($m.iterations_completed_max)"
Write-Host ("  estimated full persistent state: {0:N2} GiB" -f [double]$m.estimated_full_state_gib)
Write-Host "  last update unix: $($m.updated_at_unix)"
Write-Host ""
if ($m.stage -eq "running") {
    Write-Host "Training is running. Do not create a snapshot yet; Ctrl+C the training PowerShell once and wait for SAFE TO CLOSE first." -ForegroundColor Yellow
} elseif ($m.stage -eq "paused") {
    Write-Host "Training is safely paused. You may create a snapshot or rerun the training command to resume." -ForegroundColor Yellow
} elseif ($m.stage -eq "completed") {
    Write-Host "The 1,000-visit minimum target is complete for all exact infosets." -ForegroundColor Yellow
}
