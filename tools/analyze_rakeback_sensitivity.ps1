param(
    [string]$Snapshot = "V2_SEL2500",
    [int]$TopPerN = 3,
    [int]$Samples = 10000,
    [double]$MinEffectiveVisits = 25
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$TrainingRoot = Join-Path $RepoRoot "runs\continuous_master_fast_v2"
$AnalysisCsv = Join-Path $TrainingRoot "analysis\V2_2000_to_V2_SEL2500\task_stability.csv"

if (-not (Test-Path $AnalysisCsv)) {
    throw "Required analysis CSV not found: $AnalysisCsv"
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

Write-Host "DeepPot rakeback sensitivity audit" -ForegroundColor Green
Write-Host "  snapshot: $Snapshot"
Write-Host "  nominal rakeback: 50%"
Write-Host "  empirical PVI-factor band: 0.60, 0.70, 0.80"
Write-Host "  center estimate: 0.70 -> effective benchmark RB ~35%"
Write-Host "  read-only: CFR state, RNG and snapshots are NOT modified"
Write-Host ""

$env:PYTHONPATH = Join-Path $RepoRoot "src"
$args = @(
    (Join-Path $RepoRoot "tools\analyze_rakeback_sensitivity.py"),
    "--training-root", $TrainingRoot,
    "--snapshot", $Snapshot,
    "--analysis-csv", $AnalysisCsv,
    "--top-per-n", "$TopPerN",
    "--n-min", "5",
    "--n-max", "8",
    "--samples", "$Samples",
    "--seed", "12345",
    "--rake", "0.02",
    "--nominal-rb", "0.50",
    "--pvi-factors", "0.60,0.70,0.80",
    "--min-effective-visits", "$MinEffectiveVisits"
)

Push-Location $RepoRoot
try {
    if ($python.Count -eq 2) { & $python[0] $python[1] @args } else { & $python[0] @args }
    $code = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($code -ne 0) { throw "Rakeback sensitivity audit exited with code $code" }
