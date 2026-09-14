param(
    [string]$SnapshotName = "V2_SEL3500"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$TrainingRoot = Join-Path $RepoRoot "runs\continuous_master_fast_v2"
$SnapshotDir = Join-Path $TrainingRoot ("snapshots\" + $SnapshotName)
$OutDir = Join-Path $TrainingRoot "analysis\production_release_SEL3500"
$OutPath = Join-Path $OutDir "SEL3500_RELEASE_EQUIVALENCE.json"

if (-not (Test-Path $SnapshotDir)) {
    throw "Snapshot not found: $SnapshotDir"
}

$manifestPath = Join-Path $SnapshotDir "SNAPSHOT_MANIFEST.json"
if (-not (Test-Path $manifestPath)) {
    throw "Snapshot manifest not found: $manifestPath"
}
$manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
if ($manifest.snapshot_name -ne $SnapshotName) {
    throw "Snapshot name mismatch: $($manifest.snapshot_name) != $SnapshotName"
}
if ([int64]$manifest.exact_infosets -ne 635675248) {
    throw "Snapshot exact infoset total mismatch"
}
if (-not $manifest.ready_for_live_v5) {
    throw "Snapshot is not marked ready_for_live_v5"
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

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$env:PYTHONPATH = Join-Path $RepoRoot "src"
$args = @(
    "-m", "deeppot.continuous_runtime_equivalence",
    "--training-root", $TrainingRoot,
    "--snapshot-dir", $SnapshotDir,
    "--out", $OutPath
)

Write-Host "DeepPot D4 production release verification" -ForegroundColor Green
Write-Host "  selected policy: V2_SEL3500 greedy"
Write-Host "  snapshot: $SnapshotDir"
Write-Host "  output: $OutPath"
Write-Host "  read-only: no training state, snapshot, DLL or formula is modified"

Push-Location $RepoRoot
try {
    if ($python.Count -eq 2) { & $python[0] $python[1] @args } else { & $python[0] @args }
    $code = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($code -ne 0) { throw "SEL3500 release verifier exited with code $code" }

$result = Get-Content $OutPath -Raw | ConvertFrom-Json
if ($result.stage -ne "PASS") { throw "Release equivalence did not PASS" }
if ([int64]$result.total_infosets -ne 635675248) { throw "Release total infosets mismatch" }
if ([int64]$result.action_bit_mismatches -ne 0) { throw "Release has action bit mismatches" }
if ([int64]$result.index_metadata_mismatches -ne 0) { throw "Release has index metadata mismatches" }
if ([int64]$result.unknown_supported_keys -ne 0) { throw "Release has unknown supported keys" }

Write-Host ""
Write-Host "D4 RELEASE EQUIVALENCE PASS." -ForegroundColor Green
Write-Host ("  total infosets: {0:N0}" -f [int64]$result.total_infosets)
Write-Host ("  action bit mismatches: {0}" -f $result.action_bit_mismatches)
Write-Host ("  index metadata mismatches: {0}" -f $result.index_metadata_mismatches)
Write-Host ("  unknown supported keys: {0}" -f $result.unknown_supported_keys)
Write-Host "  snapshot manifest SHA256: $($result.snapshot_manifest_sha256)"
Write-Host "  runtime manifest SHA256:  $($result.runtime_manifest_sha256)"
Write-Host "  runtime index SHA256:     $($result.runtime_index_sha256)"
Write-Host "  result: $OutPath"
Write-Host ""
Write-Host "Do not replace the known-good i5 DeepPot.txt yet. After this PASS, deploy only the verified DeepPotRuntime folder first, then perform live scrape/action validation." -ForegroundColor Yellow
