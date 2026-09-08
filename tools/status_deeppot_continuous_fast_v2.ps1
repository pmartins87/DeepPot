$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$root = Join-Path $RepoRoot "runs\continuous_master_fast_v2"
$manifestPath = Join-Path $root "CONTINUOUS_MANIFEST.json"
if (-not (Test-Path $manifestPath)) {
    Write-Host "Fast-V2 canonical master has not started yet: $manifestPath" -ForegroundColor Yellow
    exit 0
}
$m = Get-Content $manifestPath -Raw | ConvertFrom-Json
Write-Host "DeepPot FAST V2 continuous status" -ForegroundColor Green
Write-Host "  stage: $($m.stage)"
Write-Host "  kernel: $($m.kernel)"
Write-Host "  target min visits: $($m.target_min_visits_per_infoset)"
Write-Host "  tasks with state: $($m.tasks_with_state)/$($m.tasks_total)"
Write-Host "  tasks at target: $($m.tasks_target_reached)/$($m.tasks_total)"
Write-Host "  weighted mean visits: $([math]::Round([double]$m.weighted_mean_training_visits, 2))"
Write-Host "  task min global: $($m.task_min_visit_global)"
Write-Host "  task min median: $($m.task_min_visit_median)"
Write-Host "  iterations min/median/max: $($m.iterations_completed_min) / $($m.iterations_completed_median) / $($m.iterations_completed_max)"
Write-Host "  root: $root"
