param(
    [string]$RuntimeDir = "",
    [string]$P7Result = "",
    [string]$OutDir = "",
    [string]$StayAction = "BetPot"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($RuntimeDir)) { $RuntimeDir = Join-Path $RepoRoot "runs\deeppot_runtime" }
if ([string]::IsNullOrWhiteSpace($P7Result)) { $P7Result = Join-Path $RepoRoot "runs\p7_equivalence\P7_EQUIVALENCE_RESULT.json" }
if ([string]::IsNullOrWhiteSpace($OutDir)) { $OutDir = Join-Path $RepoRoot "runs\deeppot_live" }

function Get-Sha256Lower([string]$Path) {
    return (Get-FileHash $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

if (-not (Test-Path $P7Result)) { throw "P7 result not found: $P7Result" }
$p7 = Get-Content $P7Result -Raw | ConvertFrom-Json
if ($p7.stage -ne "PASS") { throw "P7 is not PASS (stage=$($p7.stage))" }
if ([int64]$p7.total_infosets -ne 635675248) { throw "P7 total infosets mismatch" }
if ([int64]$p7.action_bit_mismatches -ne 0) { throw "P7 has action mismatches" }
if ([int64]$p7.index_metadata_mismatches -ne 0) { throw "P7 has index mismatches" }
if ([int64]$p7.unknown_supported_keys -ne 0) { throw "P7 has unknown supported keys" }

$runtimeManifestPath = Join-Path $RuntimeDir "deeppot_runtime_manifest.json"
if (-not (Test-Path $runtimeManifestPath)) { throw "runtime manifest not found: $runtimeManifestPath" }
$runtime = Get-Content $runtimeManifestPath -Raw | ConvertFrom-Json
if (-not $runtime.complete) { throw "runtime manifest is not complete" }
$runtimeManifestSha = Get-Sha256Lower $runtimeManifestPath
if ($runtimeManifestSha -ne $p7.runtime_manifest_sha256) {
    throw "P7/runtime manifest SHA mismatch"
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

if (Test-Path $OutDir) { Remove-Item $OutDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$runtimeOut = Join-Path $OutDir "DeepPotRuntime"
New-Item -ItemType Directory -Force -Path (Join-Path $runtimeOut "strategy") | Out-Null

Copy-Item (Join-Path $RuntimeDir "deeppot_runtime_index.bin") $runtimeOut -Force
Copy-Item $runtimeManifestPath $runtimeOut -Force
foreach ($n in 2..8) {
    Copy-Item (Join-Path $RuntimeDir "strategy\N${n}_final.bits") (Join-Path $runtimeOut "strategy") -Force
}

$liveFormula = Join-Path $OutDir "DeepPot.txt"
$env:PYTHONPATH = Join-Path $RepoRoot "src"
$args = @(
    "-m", "deeppot.openholdem_formula",
    "--out", $liveFormula,
    "--runtime-manifest-sha256", $runtimeManifestSha,
    "--stay-action", $StayAction,
    "--enable-live"
)
Push-Location $RepoRoot
try {
    if ($python.Count -eq 2) { & $python[0] $python[1] @args } else { & $python[0] @args }
    if ($LASTEXITCODE -ne 0) { throw "live formula generation failed with exit code $LASTEXITCODE" }
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "DEEPPOT LIVE PACKAGE PREPARED." -ForegroundColor Green
Write-Host "  P7: PASS"
Write-Host "  formula: $liveFormula"
Write-Host "  runtime folder: $runtimeOut"
Write-Host "  runtime manifest SHA256: $runtimeManifestSha"
Write-Host "  STAY action token: $StayAction"
Write-Host ""
Write-Host "Copy user.dll beside OpenHoldem.exe, copy DeepPotRuntime beside user.dll, and load DeepPot.txt." -ForegroundColor Yellow
