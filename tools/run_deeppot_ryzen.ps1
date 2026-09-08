param(
    [string]$OutDir = "",
    [int]$Workers = 0,
    [switch]$Smoke
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($OutDir)) {
    $OutDir = Join-Path $RepoRoot "runs\deepkk_parity_full"
}

$logical = [Environment]::ProcessorCount
if ($Workers -le 0) {
    # Ryzen SMT normalmente expõe 2 threads por core. O solver usa processos por flop;
    # por padrão usamos aproximadamente os cores físicos menos um, evitando oversubscription.
    $Workers = [Math]::Max(1, [Math]::Floor($logical / 2) - 1)
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

$env:PYTHONPATH = Join-Path $RepoRoot "src"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

if ($Smoke) {
    Write-Host "DeepPot Ryzen SMOKE: N=2, 1 flop, mesma cadeia de produção." -ForegroundColor Yellow
    $arguments = @(
        "-m", "deeppot.deepkk_style_streaming",
        "--out-dir", (Join-Path $OutDir "smoke"),
        "--players", "2",
        "--iterations", "20000",
        "--audit-samples", "5000",
        "--min-effective-visits", "0",
        "--seed", "123",
        "--rake-pct", "0.02",
        "--economy-profile", "provisional-2pct-uncapped",
        "--workers", "1",
        "--start-index", "0",
        "--limit", "1"
    )
} else {
    Write-Host "DeepPot FULL DeepKK-parity production run" -ForegroundColor Green
    Write-Host "  N=2..8 | 1755 flops | CFR+ | linear average | seed 123"
    Write-Host "  20,000 iterations por flop"
    Write-Host "  50,000 EV/CI95 audit samples por flop | min effective visits 25"
    Write-Host "  provisional economy: 2% rake, uncapped"
    Write-Host "  workers: $Workers (logical processors detected: $logical)"
    Write-Host "  output: $OutDir"
    Write-Host "  RESTART SAFE: execute o mesmo comando novamente para retomar checkpoints."

    $arguments = @(
        "-m", "deeppot.deepkk_style_streaming",
        "--out-dir", $OutDir,
        "--players", "2,3,4,5,6,7,8",
        "--iterations", "20000",
        "--audit-samples", "50000",
        "--min-effective-visits", "25",
        "--seed", "123",
        "--rake-pct", "0.02",
        "--economy-profile", "provisional-2pct-uncapped",
        "--workers", "$Workers"
    )
}

Push-Location $RepoRoot
try {
    if ($python.Count -eq 2) {
        & $python[0] $python[1] @arguments
    } else {
        & $python[0] @arguments
    }
    if ($LASTEXITCODE -ne 0) {
        throw "DeepPot trainer terminou com exit code $LASTEXITCODE"
    }
} finally {
    Pop-Location
}

if (-not $Smoke) {
    Write-Host "";
    Write-Host "TREINO CONCLUÍDO." -ForegroundColor Green
    Write-Host "Arquivos principais:"
    Write-Host "  $OutDir\DeepPot.txt"
    Write-Host "  $OutDir\scenario_catalog_494.csv"
    Write-Host "  $OutDir\RUN_MANIFEST.json"
    Write-Host "  $OutDir\N2..N8\compiled\*.bits + *_index.json"
}
