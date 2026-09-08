param(
    [string]$RunDir = "",
    [string]$OutDir = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($RunDir)) {
    $RunDir = Join-Path $RepoRoot "runs\deepkk_parity_full"
}
if ([string]::IsNullOrWhiteSpace($OutDir)) {
    $OutDir = Join-Path $RepoRoot "runs\deeppot_runtime"
}

$manifestPath = Join-Path $RunDir "RUN_MANIFEST.json"
if (-not (Test-Path $manifestPath)) {
    throw "RUN_MANIFEST.json não encontrado em $RunDir"
}
$runManifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
if ($runManifest.stage -ne "completed") {
    throw "A run matemática ainda não está concluída (stage=$($runManifest.stage)). Não compile um runtime parcial."
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
    throw "Python 3.11+ não encontrado."
}

$env:PYTHONPATH = Join-Path $RepoRoot "src"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

Write-Host "DeepPot: compilando a base matemática completa para o runtime OpenHoldem..." -ForegroundColor Green
Write-Host "  source run: $RunDir"
Write-Host "  runtime:    $OutDir"

$packageArgs = @(
    "-m", "deeppot.runtime_package",
    "--run-dir", $RunDir,
    "--out-dir", $OutDir
)
Push-Location $RepoRoot
try {
    if ($python.Count -eq 2) {
        & $python[0] $python[1] @packageArgs
    } else {
        & $python[0] @packageArgs
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Compilação do runtime terminou com exit code $LASTEXITCODE"
    }
} finally {
    Pop-Location
}

$runtimeManifest = Join-Path $OutDir "deeppot_runtime_manifest.json"
if (-not (Test-Path $runtimeManifest)) {
    throw "Runtime manifest não foi produzido."
}
$runtimeHash = (Get-FileHash $runtimeManifest -Algorithm SHA256).Hash.ToLowerInvariant()

$formulaPath = Join-Path $OutDir "DeepPot_operational_DISABLED.txt"
$formulaArgs = @(
    "-m", "deeppot.openholdem_formula",
    "--out", $formulaPath,
    "--runtime-manifest-sha256", $runtimeHash,
    "--stay-action", "BetPot"
)
Push-Location $RepoRoot
try {
    if ($python.Count -eq 2) {
        & $python[0] $python[1] @formulaArgs
    } else {
        & $python[0] @formulaArgs
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Geração da fórmula operacional terminou com exit code $LASTEXITCODE"
    }
} finally {
    Pop-Location
}

$runtimeManifestObject = Get-Content $runtimeManifest -Raw | ConvertFrom-Json
if (-not $runtimeManifestObject.complete) {
    throw "Runtime produzido não está marcado como completo."
}

Write-Host ""
Write-Host "RUNTIME OFFLINE COMPILADO COM SUCESSO." -ForegroundColor Green
Write-Host "  manifest: $runtimeManifest"
Write-Host "  manifest SHA256: $runtimeHash"
Write-Host "  index: $(Join-Path $OutDir 'deeppot_runtime_index.bin')"
Write-Host "  strategy: $(Join-Path $OutDir 'strategy')"
Write-Host "  formula segura/desabilitada: $formulaPath"
Write-Host ""
Write-Host "A fórmula permanece com f`$deeppot_live_enabled=false." -ForegroundColor Yellow
Write-Host "Não habilite autoplayer antes da validação do tablemap, histórico FOLD/STAY e botão STAY/POT."
