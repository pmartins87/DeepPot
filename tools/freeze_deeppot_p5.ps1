param(
    [string]$RunDir = "",
    [string]$RuntimeDir = "",
    [string]$OutDir = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($RunDir)) { $RunDir = Join-Path $RepoRoot "runs\deepkk_parity_full" }
if ([string]::IsNullOrWhiteSpace($RuntimeDir)) { $RuntimeDir = Join-Path $RepoRoot "runs\deeppot_runtime" }
if ([string]::IsNullOrWhiteSpace($OutDir)) { $OutDir = Join-Path $RepoRoot "runs\p5_freeze" }

function Get-Sha256Lower([string]$Path) {
    return (Get-FileHash $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

$runManifestPath = Join-Path $RunDir "RUN_MANIFEST.json"
$runtimeManifestPath = Join-Path $RuntimeDir "deeppot_runtime_manifest.json"
if (-not (Test-Path $runManifestPath)) { throw "RUN_MANIFEST.json nao encontrado: $runManifestPath" }
if (-not (Test-Path $runtimeManifestPath)) { throw "Runtime manifest nao encontrado: $runtimeManifestPath" }

$run = Get-Content $runManifestPath -Raw | ConvertFrom-Json
$runtime = Get-Content $runtimeManifestPath -Raw | ConvertFrom-Json
if ($run.stage -ne "completed") { throw "P4 nao esta completed (stage=$($run.stage))" }
if (-not $runtime.complete) { throw "Runtime nao esta marcado complete" }
if ([int]$runtime.flops -ne 1755) { throw "Runtime nao contem 1755 flops" }

$actualRunSha = Get-Sha256Lower $runManifestPath
if ($runtime.source_run_manifest_sha256 -ne $actualRunSha) {
    throw "Runtime foi compilado de outro RUN_MANIFEST: $($runtime.source_run_manifest_sha256) != $actualRunSha"
}

$artifacts = New-Object System.Collections.Generic.List[object]
function Add-Artifact([string]$Role, [string]$Path) {
    if (-not (Test-Path $Path)) { throw "Artefato obrigatorio ausente: $Path" }
    $item = Get-Item $Path
    $rel = [System.IO.Path]::GetRelativePath($RepoRoot, $item.FullName)
    $artifacts.Add([ordered]@{
        role = $Role
        path = $rel
        bytes = [int64]$item.Length
        sha256 = Get-Sha256Lower $item.FullName
    })
}

Add-Artifact "p4_run_manifest" $runManifestPath
Add-Artifact "mathematical_txt" (Join-Path $RunDir "DeepPot.txt")
Add-Artifact "scenario_catalog_494" (Join-Path $RunDir "scenario_catalog_494.csv")

$rows = New-Object System.Collections.Generic.List[object]
$totalExpected = [int64]0
$totalConfident = [int64]0
$totalLowCoverage = [int64]0
$totalStay = [int64]0
$totalOverrides = [int64]0

foreach ($n in 2..8) {
    $mr = $run.mode_results."$n"
    if ($null -eq $mr) { throw "mode_results N=$n ausente" }
    if ([int]$mr.flops -ne 1755) { throw "N=$n nao tem 1755 flops" }

    $expected = [int64]$mr.expected_infosets
    $confident = [int64]$mr.confident_infosets
    $low = [int64]$mr.low_coverage_infosets
    $stay = [int64]$mr.final_stay_infosets
    $overrides = [int64]$mr.confident_ev_overrides

    $totalExpected += $expected
    $totalConfident += $confident
    $totalLowCoverage += $low
    $totalStay += $stay
    $totalOverrides += $overrides

    $rows.Add([ordered]@{
        N = $n
        flops = 1755
        infosets = $expected
        confident = $confident
        confident_pct = [math]::Round(100.0 * $confident / $expected, 4)
        low_coverage = $low
        low_coverage_pct = [math]::Round(100.0 * $low / $expected, 4)
        final_stay = $stay
        final_stay_pct = [math]::Round(100.0 * $stay / $expected, 4)
        confident_ev_overrides = $overrides
        solve_seconds_sum = [double]$mr.solve_seconds_sum
        audit_seconds_sum = [double]$mr.audit_seconds_sum
    })

    $compiled = Join-Path $RunDir "N$n\compiled"
    Add-Artifact "N${n}_index" (Join-Path $compiled "N${n}_index.json")
    foreach ($kind in @("final", "solver", "confident", "low_coverage")) {
        Add-Artifact "N${n}_${kind}_bits" (Join-Path $compiled "N${n}_${kind}.bits")
    }
    Add-Artifact "N${n}_audit_summary" (Join-Path $RunDir "N$n\audit_summary.json")
}

Add-Artifact "runtime_manifest" $runtimeManifestPath
Add-Artifact "runtime_index" (Join-Path $RuntimeDir "deeppot_runtime_index.bin")
foreach ($n in 2..8) {
    $path = Join-Path $RuntimeDir "strategy\N${n}_final.bits"
    Add-Artifact "runtime_N${n}_final_bits" $path
    $actual = Get-Sha256Lower $path
    $expected = $runtime.modes."$n".sha256
    if ($actual -ne $expected) { throw "Runtime N=$n SHA mismatch" }
}
Add-Artifact "operational_formula_disabled" (Join-Path $RuntimeDir "DeepPot_operational_DISABLED.txt")

if ($totalExpected -ne 635675248) {
    throw "Total de infosets inesperado: $totalExpected != 635675248"
}

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$freeze = [ordered]@{
    format = "DeepPot P5 immutable mathematical-source freeze manifest"
    freeze_version = "2026-09-08.1"
    stage = "frozen"
    source_run_stage = $run.stage
    source_run_manifest_sha256 = $actualRunSha
    source_generator_sha256 = $run.source_sha256
    seed = $run.seed
    economy_profile = $run.economy_profile
    iterations_per_flop = $run.iterations_per_flop
    audit_samples_per_flop = $run.audit_samples_per_flop
    min_effective_visits = $run.min_effective_visits
    workers = $run.workers
    canonical_flops_per_mode = $run.selected_flops
    elapsed_seconds = [double]$run.elapsed_seconds
    total_infosets = $totalExpected
    total_confident_infosets = $totalConfident
    total_confident_pct = [math]::Round(100.0 * $totalConfident / $totalExpected, 4)
    total_low_coverage_infosets = $totalLowCoverage
    total_low_coverage_pct = [math]::Round(100.0 * $totalLowCoverage / $totalExpected, 4)
    total_final_stay_infosets = $totalStay
    total_final_stay_pct = [math]::Round(100.0 * $totalStay / $totalExpected, 4)
    total_confident_ev_overrides = $totalOverrides
    runtime_manifest_sha256 = Get-Sha256Lower $runtimeManifestPath
    runtime_index_sha256 = Get-Sha256Lower (Join-Path $RuntimeDir "deeppot_runtime_index.bin")
    modes = $rows
    artifacts = $artifacts
}

$freezePath = Join-Path $OutDir "P5_FREEZE_MANIFEST.json"
$freeze | ConvertTo-Json -Depth 8 | Set-Content -Path $freezePath -Encoding UTF8
$freezeSha = Get-Sha256Lower $freezePath

Write-Host ""
Write-Host "P4/P5 FINAL REVIEW" -ForegroundColor Green
Write-Host ("  elapsed: {0:N1} s = {1:N2} h" -f [double]$run.elapsed_seconds, ([double]$run.elapsed_seconds / 3600.0))
Write-Host ""
$rows | Format-Table N,infosets,confident_pct,low_coverage_pct,final_stay_pct,confident_ev_overrides -AutoSize
Write-Host ("TOTAL infosets: {0:N0}" -f $totalExpected)
Write-Host ("TOTAL confident: {0:N0} ({1:N4}%)" -f $totalConfident, (100.0*$totalConfident/$totalExpected))
Write-Host ("TOTAL low coverage: {0:N0} ({1:N4}%)" -f $totalLowCoverage, (100.0*$totalLowCoverage/$totalExpected))
Write-Host ("TOTAL final STAY: {0:N0} ({1:N4}%)" -f $totalStay, (100.0*$totalStay/$totalExpected))
Write-Host ("TOTAL confident EV overrides: {0:N0}" -f $totalOverrides)
Write-Host ""
Write-Host "P5 FREEZE MANIFEST CRIADO." -ForegroundColor Green
Write-Host "  $freezePath"
Write-Host "  SHA256: $freezeSha"
Write-Host ""
Write-Host "Nao altere nem apague runs\deepkk_parity_full, runs\deeppot_runtime ou runs\p5_freeze." -ForegroundColor Yellow
