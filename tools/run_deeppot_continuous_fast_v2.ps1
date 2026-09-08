param(
    [string]$OutDir = "",
    [int]$TargetMinVisits = 1000,
    [int]$ChunkIterations = 50000,
    [int]$Workers = 31,
    [double]$MaxWallHours = 0,
    [double]$MinFreeGiB = 30
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($OutDir)) {
    $OutDir = Join-Path $RepoRoot "runs\continuous_master_fast_v2"
}

$logical = [Environment]::ProcessorCount
if ($Workers -le 0) { $Workers = 31 }

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

Write-Host "DeepPot CONTINUOUS FAST V2 canonical deep training" -ForegroundColor Green
Write-Host "  kernel: FastChanceSampledCFRV2"
Write-Host "  target: EVERY exact infoset >= $TargetMinVisits training visits"
Write-Host "  N=2..8 | 1,755 canonical flops | 635,675,248 exact infosets"
Write-Host "  CFR+ | linear average | seed 123 | provisional 2% uncapped rake"
Write-Host "  chunk: $($ChunkIterations.ToString('N0')) iterations per task before atomic checkpoint"
Write-Host "  workers: $Workers / logical processors: $logical"
Write-Host "  worker source: fast-V2 Ryzen scaling winner"
Write-Host "  persistent state: $OutDir"
Write-Host "  pilot root C:\DeepPot\runs\continuous_master is NOT touched"
Write-Host "  EV audit: intentionally disabled for this deep track"
Write-Host ""
Write-Host "INTERRUPTION:" -ForegroundColor Yellow
Write-Host "  Press Ctrl+C once. New chunks stop; active chunks finish and checkpoint."
Write-Host "  Wait for 'SAFE TO CLOSE' before closing PowerShell or shutting down."
Write-Host "  Run THIS SAME COMMAND later to resume the exact CFR/RNG trajectory."
Write-Host ""

$env:PYTHONPATH = Join-Path $RepoRoot "src"
$args = @(
    "-m", "deeppot.continuous_runner_fast_v2",
    "--out", $OutDir,
    "--target-min-visits", "$TargetMinVisits",
    "--chunk-iterations", "$ChunkIterations",
    "--workers", "$Workers",
    "--seed", "123",
    "--rake", "0.02",
    "--max-wall-hours", "$MaxWallHours",
    "--min-free-gib", "$MinFreeGiB"
)

Push-Location $RepoRoot
try {
    if ($python.Count -eq 2) { & $python[0] $python[1] @args } else { & $python[0] @args }
    $code = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($code -ne 0) { throw "DeepPot FAST V2 continuous trainer exited with code $code" }
