param(
    [double]$MinFreeGiB = 30
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

Write-Host "DeepPot CONTINUOUS TRAINING PREFLIGHT" -ForegroundColor Green
Write-Host "  repo: $RepoRoot"

$required = @(
    "runs\deepkk_parity_full\RUN_MANIFEST.json",
    "runs\deeppot_runtime\deeppot_runtime_index.bin",
    "runs\p5_freeze\P5_FREEZE_MANIFEST.json",
    "tools\run_deeppot_continuous.ps1",
    "tools\snapshot_deeppot_continuous.ps1",
    "tools\status_deeppot_continuous.ps1",
    "tools\check_deeppot_continuous_resume.py"
)
foreach ($rel in $required) {
    $path = Join-Path $RepoRoot $rel
    if (-not (Test-Path $path)) { throw "Required file missing: $path" }
}

$base = Get-Content (Join-Path $RepoRoot "runs\deepkk_parity_full\RUN_MANIFEST.json") -Raw | ConvertFrom-Json
if ($base.stage -ne "completed") { throw "Base v1 source run is not completed" }

$freezePath = Join-Path $RepoRoot "runs\p5_freeze\P5_FREEZE_MANIFEST.json"
$freezeHash = (Get-FileHash $freezePath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($freezeHash -ne "4d4077796ce81ec4d74a99818d69cc999221ad77c973c7d6fe7d4102d1a43a8a") {
    throw "Base v1 P5 freeze hash mismatch: $freezeHash"
}
Write-Host "  Base v1 freeze: PASS ($freezeHash)"

$workerPath = Join-Path $RepoRoot "runs\worker_benchmark\selected_workers.txt"
if (-not (Test-Path $workerPath)) { throw "Frozen worker benchmark result missing: $workerPath" }
$workers = (Get-Content $workerPath -Raw).Trim()
if ($workers -ne "31") { throw "Expected frozen worker count 31, got: $workers" }
Write-Host "  workers: PASS (31)"

$driveRoot = [System.IO.Path]::GetPathRoot($RepoRoot)
$drive = New-Object System.IO.DriveInfo($driveRoot)
$freeGiB = $drive.AvailableFreeSpace / 1GB
Write-Host ("  free disk: {0:N2} GiB" -f $freeGiB)
if ($freeGiB -lt $MinFreeGiB) {
    throw ("Need at least {0:N2} GiB free before a new continuous master; available {1:N2} GiB" -f $MinFreeGiB, $freeGiB)
}

$pythonCmd = $null
try {
    & py -3.11 -c "import sys; assert sys.version_info >= (3,11)" *> $null
    if ($LASTEXITCODE -eq 0) { $pythonCmd = @("py", "-3.11") }
} catch {}
if ($null -eq $pythonCmd) {
    try {
        & python -c "import sys; assert sys.version_info >= (3,11)" *> $null
        if ($LASTEXITCODE -eq 0) { $pythonCmd = @("python") }
    } catch {}
}
if ($null -eq $pythonCmd) { throw "Python 3.11+ not found" }

$smoke = Join-Path $RepoRoot "tools\check_deeppot_continuous_resume.py"
Write-Host "  running exact resume smoke..."
Push-Location $RepoRoot
try {
    if ($pythonCmd.Count -eq 2) { & $pythonCmd[0] $pythonCmd[1] $smoke } else { & $pythonCmd[0] $smoke }
    $code = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($code -ne 0) { throw "Continuous exact-resume smoke failed with exit code $code" }

$master = Join-Path $RepoRoot "runs\continuous_master"
if (Test-Path $master) {
    $items = @(Get-ChildItem $master -Force -ErrorAction SilentlyContinue)
    if ($items.Count -gt 0) {
        Write-Host "  NOTE: runs\continuous_master already contains state. This is a RESUME, not a fresh master." -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "DEEPPOT CONTINUOUS PREFLIGHT: PASS" -ForegroundColor Green
Write-Host "  target launcher is ready; this preflight did NOT start the long run."
Write-Host "  next command when authorized:"
Write-Host "  powershell -ExecutionPolicy Bypass -File C:\DeepPot\tools\run_deeppot_continuous.ps1" -ForegroundColor Yellow
