param(
    [string]$OutDir = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$SnapshotRoot = Join-Path $RepoRoot "runs\continuous_master_fast_v2\snapshots\V2_SEL3500"
$SourceRuntime = Join-Path $SnapshotRoot "DeepPotRuntime"
$ReleaseResult = Join-Path $RepoRoot "runs\continuous_master_fast_v2\analysis\production_release_SEL3500\SEL3500_RELEASE_EQUIVALENCE.json"
$Verifier = Join-Path $RepoRoot "tools\verify_deeppot_sel3500_runtime_folder.ps1"

if ([string]::IsNullOrWhiteSpace($OutDir)) {
    $OutDir = Join-Path $RepoRoot "runs\production_release_SEL3500"
}

if (-not (Test-Path $SourceRuntime -PathType Container)) {
    throw "SEL3500 snapshot runtime not found: $SourceRuntime"
}
if (-not (Test-Path $ReleaseResult -PathType Leaf)) {
    throw "D4 release-equivalence result not found: $ReleaseResult"
}
if (-not (Test-Path $Verifier -PathType Leaf)) {
    throw "Frozen runtime verifier not found: $Verifier"
}

$result = Get-Content $ReleaseResult -Raw | ConvertFrom-Json
if ($result.stage -ne "PASS") { throw "D4 release-equivalence is not PASS" }
if ($result.snapshot_name -ne "V2_SEL3500") { throw "Unexpected snapshot in D4 result: $($result.snapshot_name)" }
if ([int64]$result.total_infosets -ne 635675248) { throw "Unexpected total infosets in D4 result" }
if ([int64]$result.action_bit_mismatches -ne 0) { throw "D4 has action bit mismatches" }
if ([int64]$result.index_metadata_mismatches -ne 0) { throw "D4 has index metadata mismatches" }
if ([int64]$result.unknown_supported_keys -ne 0) { throw "D4 has unknown supported keys" }
if ($result.runtime_manifest_sha256 -ne "717c2fd0582e91d293b92fea1fc7355524681976a6856b8c5b6e70e2b3e01158") {
    throw "D4 runtime manifest SHA does not match the frozen SEL3500 release"
}
if ($result.runtime_index_sha256 -ne "fb8bff8f21efd253ec6374de920de74d9fa662df673d5cd579f68fad152b6f74") {
    throw "D4 runtime index SHA does not match the frozen SEL3500 release"
}

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$PackageDir = Join-Path $OutDir "DeepPot_SEL3500_RUNTIME_ONLY"
$ZipPath = Join-Path $OutDir "DeepPot_SEL3500_RUNTIME_ONLY.zip"

if (Test-Path $PackageDir) { Remove-Item $PackageDir -Recurse -Force }
if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
New-Item -ItemType Directory -Force -Path $PackageDir | Out-Null

$RuntimeDest = Join-Path $PackageDir "DeepPotRuntime"
Copy-Item $SourceRuntime $RuntimeDest -Recurse -Force
Copy-Item $Verifier (Join-Path $PackageDir "VERIFY_SEL3500_RUNTIME.ps1") -Force

$readme = @"
DeepPot V2_SEL3500 GREEDY - RUNTIME-ONLY PRODUCTION DEPLOYMENT
Date: 2026-09-14

This package intentionally contains ONLY:
- DeepPotRuntime\ (the frozen SEL3500 greedy runtime)
- VERIFY_SEL3500_RUNTIME.ps1
- this README

DO NOT replace the known-good i5 DeepPot.txt, user.dll, or tablemap as part of this deployment.
The policy/runtime release passed exhaustive D4 equivalence over 635,675,248 exact infosets with:
- action bit mismatches: 0
- index metadata mismatches: 0
- unknown supported keys: 0

Frozen hashes:
- runtime manifest: 717c2fd0582e91d293b92fea1fc7355524681976a6856b8c5b6e70e2b3e01158
- runtime index:    fb8bff8f21efd253ec6374de920de74d9fa662df673d5cd579f68fad152b6f74

On the i5, BEFORE replacing anything, close OpenHoldem and back up the current DeepPotRuntime folder.
After copying this package, verify it with:

powershell -ExecutionPolicy Bypass -File .\VERIFY_SEL3500_RUNTIME.ps1 -RuntimeDir .\DeepPotRuntime

Only after HASH VERIFICATION PASS should the existing live DeepPotRuntime folder be replaced.
Live scraping/action validation is a separate final gate; this package does not claim to validate the tablemap or scraper.
"@
$readme | Set-Content -Path (Join-Path $PackageDir "README_RUNTIME_ONLY.txt") -Encoding UTF8

Write-Host "Verifying staged runtime before packaging..." -ForegroundColor Green
& $Verifier -RuntimeDir $RuntimeDest
if ($LASTEXITCODE -ne 0) { throw "Runtime verifier returned exit code $LASTEXITCODE" }

Compress-Archive -Path (Join-Path $PackageDir "*") -DestinationPath $ZipPath -CompressionLevel Optimal
$zipSha = (Get-FileHash $ZipPath -Algorithm SHA256).Hash.ToLowerInvariant()
$zipBytes = (Get-Item $ZipPath).Length

Write-Host ""
Write-Host "SEL3500 RUNTIME-ONLY DEPLOYMENT PACKAGE READY." -ForegroundColor Green
Write-Host "  folder: $PackageDir"
Write-Host "  zip:    $ZipPath"
Write-Host "  bytes:  $zipBytes"
Write-Host "  zip SHA256: $zipSha"
Write-Host ""
Write-Host "Transfer this ZIP to the i5. Do not deploy DeepPot.txt or user.dll from the snapshot." -ForegroundColor Yellow
