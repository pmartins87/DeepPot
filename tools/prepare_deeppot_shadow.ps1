param(
    [string]$RuntimeDir = "",
    [string]$P7Result = "",
    [string]$OutDir = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($RuntimeDir)) { $RuntimeDir = Join-Path $RepoRoot "runs\deeppot_runtime" }
if ([string]::IsNullOrWhiteSpace($P7Result)) { $P7Result = Join-Path $RepoRoot "runs\p7_equivalence\P7_EQUIVALENCE_RESULT.json" }
if ([string]::IsNullOrWhiteSpace($OutDir)) { $OutDir = Join-Path $RepoRoot "runs\deeppot_shadow" }

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
    throw "P7/runtime manifest SHA mismatch: $($p7.runtime_manifest_sha256) != $runtimeManifestSha"
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
    $src = Join-Path $RuntimeDir "strategy\N${n}_final.bits"
    if (-not (Test-Path $src)) { throw "missing runtime bitset: $src" }
    Copy-Item $src (Join-Path $runtimeOut "strategy") -Force
}

$shadowFormula = Join-Path $OutDir "DeepPot_SHADOW_SAFE.txt"
$env:PYTHONPATH = Join-Path $RepoRoot "src"
$args = @(
    "-m", "deeppot.openholdem_shadow_formula",
    "--out", $shadowFormula,
    "--runtime-manifest-sha256", $runtimeManifestSha
)
Push-Location $RepoRoot
try {
    if ($python.Count -eq 2) { & $python[0] $python[1] @args } else { & $python[0] @args }
    if ($LASTEXITCODE -ne 0) { throw "shadow formula generation failed with exit code $LASTEXITCODE" }
} finally {
    Pop-Location
}

$readme = @"
DEEPPOT SHADOW PACKAGE — P8 PREPARATION

P7: PASS
Total exact infosets: 635,675,248
Runtime manifest SHA256: $runtimeManifestSha
Runtime index SHA256: $($p7.runtime_index_sha256)

Contents:
- DeepPot_SHADOW_SAFE.txt
- DeepPotRuntime\deeppot_runtime_index.bin
- DeepPotRuntime\deeppot_runtime_manifest.json
- DeepPotRuntime\strategy\N2_final.bits ... N8_final.bits

This package intentionally does NOT enable live actions.
DeepPot_SHADOW_SAFE.txt contains no Fold/Call/Bet/Raise/Allin action commands.
Keep OpenHoldem Autoplayer OFF.
In Formula Editor -> Debug, press Auto. This evaluates dll`$deeppot_action once per heartbeat.
The DeepPot user.dll then logs [DeepPot] HIT/MISS and the recommended encoded action.

Still required before P8 can begin:
1. put the validated Pot Fold tablemap in OpenHoldem;
2. put the compiled DeepPot user.dll in the OpenHoldem executable directory;
3. copy the DeepPotRuntime directory beside user.dll;
4. load DeepPot_SHADOW_SAFE.txt;
5. keep Autoplayer OFF and validate live scrape/action-order state.
"@
Set-Content -Path (Join-Path $OutDir "SHADOW_README.txt") -Value $readme -Encoding UTF8

Write-Host ""
Write-Host "DEEPPOT SHADOW PACKAGE PREPARED." -ForegroundColor Green
Write-Host "  P7: PASS"
Write-Host "  total exact infosets: 635,675,248"
Write-Host "  formula: $shadowFormula"
Write-Host "  runtime folder: $runtimeOut"
Write-Host "  readme: $(Join-Path $OutDir 'SHADOW_README.txt')"
Write-Host ""
Write-Host "Autoplayer must remain OFF. This shadow formula contains no poker action commands." -ForegroundColor Yellow
