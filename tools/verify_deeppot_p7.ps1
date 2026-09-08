param(
    [string]$RunDir = "",
    [string]$RuntimeDir = "",
    [string]$OutPath = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($RunDir)) { $RunDir = Join-Path $RepoRoot "runs\deepkk_parity_full" }
if ([string]::IsNullOrWhiteSpace($RuntimeDir)) { $RuntimeDir = Join-Path $RepoRoot "runs\deeppot_runtime" }
if ([string]::IsNullOrWhiteSpace($OutPath)) { $OutPath = Join-Path $RepoRoot "runs\p7_equivalence\P7_EQUIVALENCE_RESULT.json" }

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
if ($null -eq $python) { throw "Python 3.11+ nao encontrado." }

$env:PYTHONPATH = Join-Path $RepoRoot "src"
$argsList = @(
    "-m", "deeppot.runtime_equivalence",
    "--run-dir", $RunDir,
    "--runtime-dir", $RuntimeDir,
    "--out", $OutPath
)

Write-Host "DeepPot P7: verificando equivalencia matematica -> runtime..." -ForegroundColor Green
Write-Host "  source:  $RunDir"
Write-Host "  runtime: $RuntimeDir"
Write-Host "  output:  $OutPath"

Push-Location $RepoRoot
try {
    if ($python.Count -eq 2) {
        & $python[0] $python[1] @argsList
    } else {
        & $python[0] @argsList
    }
    if ($LASTEXITCODE -ne 0) { throw "P7 terminou com exit code $LASTEXITCODE" }
} finally {
    Pop-Location
}

$result = Get-Content $OutPath -Raw | ConvertFrom-Json
if ($result.stage -ne "PASS") { throw "P7 nao passou (stage=$($result.stage))" }

Write-Host ""
Write-Host "P7 PASS." -ForegroundColor Green
Write-Host ("  total infosets: {0:N0}" -f [int64]$result.total_infosets)
Write-Host ("  structurally resolvable: {0:N0}" -f [int64]$result.structurally_resolvable_infosets)
Write-Host ("  unknown supported keys: {0}" -f $result.unknown_supported_keys)
Write-Host ("  action bit mismatches: {0}" -f $result.action_bit_mismatches)
Write-Host ("  index metadata mismatches: {0}" -f $result.index_metadata_mismatches)
Write-Host "  result: $OutPath"
