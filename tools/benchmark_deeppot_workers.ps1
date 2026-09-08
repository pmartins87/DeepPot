param(
    [string]$OutDir = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($OutDir)) {
    $OutDir = Join-Path $RepoRoot "runs\worker_benchmark"
}

$python = $null
try {
    & py -3.11 -c "import sys; print(sys.version)" *> $null
    if ($LASTEXITCODE -eq 0) { $python = @("py", "-3.11") }
} catch {}
if ($null -eq $python) {
    try {
        & python -c "import sys; assert sys.version_info >= (3,11); print(sys.version)" *> $null
        if ($LASTEXITCODE -eq 0) { $python = @("python") }
    } catch {}
}
if ($null -eq $python) {
    throw "Python 3.11+ não encontrado. Instale Python 3.11/3.12 e execute novamente."
}

$logical = [Environment]::ProcessorCount
$low = [Math]::Max(1, [Math]::Floor($logical / 2) - 1)
$mid = [Math]::Max(1, [Math]::Floor((3 * $logical) / 4) - 1)
$high = [Math]::Max(1, $logical - 1)
$candidates = @($low, $mid, $high) | Sort-Object -Unique
$candidateText = ($candidates -join ",")

$env:PYTHONPATH = Join-Path $RepoRoot "src"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$outJson = Join-Path $OutDir "worker_benchmark.json"
$outSelected = Join-Path $OutDir "selected_workers.txt"

Write-Host "DeepPot finite Ryzen worker benchmark" -ForegroundColor Green
Write-Host "  logical processors: $logical"
Write-Host "  candidates: $candidateText"
Write-Host "  fixed workload: N=8, 64 evenly spread canonical flops"
Write-Host "  3,000 CFR+ iterations + 3,000 exact EV-audit samples per flop"
Write-Host "  one pass per candidate; fastest wall time wins"
Write-Host "  output: $OutDir"
Write-Host ""

$arguments = @(
    "-m", "deeppot.worker_benchmark",
    "--candidates", $candidateText,
    "--jobs", "64",
    "--iterations", "3000",
    "--audit-samples", "3000",
    "--seed", "123",
    "--out-json", $outJson,
    "--out-selected", $outSelected
)

Push-Location $RepoRoot
try {
    if ($python.Count -eq 2) {
        & $python[0] $python[1] @arguments
    } else {
        & $python[0] @arguments
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Worker benchmark terminou com exit code $LASTEXITCODE"
    }
} finally {
    Pop-Location
}

$selected = (Get-Content $outSelected -Raw).Trim()
Write-Host ""
Write-Host "BENCHMARK CONCLUÍDO: $selected workers selecionados." -ForegroundColor Green
Write-Host "O trainer oficial lerá automaticamente $outSelected se -Workers não for informado."
