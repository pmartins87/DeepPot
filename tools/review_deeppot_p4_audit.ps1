param(
    [string]$RunDir = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($RunDir)) {
    $RunDir = Join-Path $RepoRoot "runs\deepkk_parity_full"
}

$manifestPath = Join-Path $RunDir "RUN_MANIFEST.json"
if (-not (Test-Path $manifestPath)) {
    throw "RUN_MANIFEST.json nao encontrado: $manifestPath"
}
$run = Get-Content $manifestPath -Raw | ConvertFrom-Json
if ($run.stage -ne "completed") {
    throw "Run nao esta completed (stage=$($run.stage))"
}

$rows = New-Object System.Collections.Generic.List[object]
$totalInfosets = [int64]0
$totalCovered = [int64]0
$totalLow = [int64]0
$totalConfident = [int64]0
$totalStay = [int64]0
$totalOverrides = [int64]0

foreach ($n in 2..8) {
    $summaryPath = Join-Path $RunDir "N$n\audit_summary.json"
    if (-not (Test-Path $summaryPath)) {
        throw "audit_summary ausente para N=$n: $summaryPath"
    }
    $summaries = @(Get-Content $summaryPath -Raw | ConvertFrom-Json)
    if ($summaries.Count -ne 1755) {
        throw "N=$n audit_summary deveria ter 1755 flops, mas tem $($summaries.Count)"
    }

    $infosets = [int64]0
    $covered = [int64]0
    $low = [int64]0
    $confident = [int64]0
    $stay = [int64]0
    $overrides = [int64]0

    foreach ($s in $summaries) {
        $infosets += [int64]$s.total_infosets
        $covered += [int64]$s.covered_infosets
        $low += [int64]$s.low_coverage_infosets
        $confident += [int64]$s.confident_best_action_infosets
        $stay += [int64]$s.final_stay_infosets
        $overrides += [int64]$s.confident_ev_overrides
    }

    $adequate = $infosets - $low
    $rows.Add([pscustomobject][ordered]@{
        N = $n
        infosets = $infosets
        covered_pct = [math]::Round(100.0 * $covered / $infosets, 4)
        low_coverage_pct = [math]::Round(100.0 * $low / $infosets, 4)
        adequate_infosets = $adequate
        confident_pct = [math]::Round(100.0 * $confident / $infosets, 4)
        confident_of_adequate_pct = if ($adequate -gt 0) { [math]::Round(100.0 * $confident / $adequate, 4) } else { 0.0 }
        final_stay_pct = [math]::Round(100.0 * $stay / $infosets, 4)
        confident_ev_overrides = $overrides
    })

    $totalInfosets += $infosets
    $totalCovered += $covered
    $totalLow += $low
    $totalConfident += $confident
    $totalStay += $stay
    $totalOverrides += $overrides
}

if ($totalInfosets -ne 635675248) {
    throw "Total de infosets inesperado: $totalInfosets"
}

$totalAdequate = $totalInfosets - $totalLow

Write-Host ""
Write-Host "DEEPPOT P4 AUDIT REVIEW (READ-ONLY)" -ForegroundColor Green
Write-Host ""
$rows | Format-Table N,infosets,covered_pct,low_coverage_pct,confident_pct,confident_of_adequate_pct,final_stay_pct,confident_ev_overrides -AutoSize
Write-Host ""
Write-Host ("TOTAL infosets: {0:N0}" -f $totalInfosets)
Write-Host ("TOTAL covered at least once: {0:N0} ({1:N4}%)" -f $totalCovered, (100.0*$totalCovered/$totalInfosets))
Write-Host ("TOTAL low coverage: {0:N0} ({1:N4}%)" -f $totalLow, (100.0*$totalLow/$totalInfosets))
Write-Host ("TOTAL adequate coverage: {0:N0} ({1:N4}%)" -f $totalAdequate, (100.0*$totalAdequate/$totalInfosets))
Write-Host ("TOTAL confident: {0:N0} ({1:N4}% of all; {2:N4}% of adequate)" -f $totalConfident, (100.0*$totalConfident/$totalInfosets), $(if ($totalAdequate -gt 0) {100.0*$totalConfident/$totalAdequate} else {0.0}))
Write-Host ("TOTAL final STAY: {0:N0} ({1:N4}%)" -f $totalStay, (100.0*$totalStay/$totalInfosets))
Write-Host ("TOTAL confident EV overrides: {0:N0}" -f $totalOverrides)
Write-Host ""
Write-Host "Este script nao altera nenhum arquivo de estrategia, runtime ou freeze." -ForegroundColor Yellow
