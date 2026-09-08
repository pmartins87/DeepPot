param(
    [int]$Iterations = 5000,
    [int]$Warmup = 200,
    [int]$FlopIndex = 877
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $RepoRoot "src"

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

$out = Join-Path $RepoRoot "runs\kernel_benchmark_fast"
$args = @(
    (Join-Path $PSScriptRoot "benchmark_deeppot_fast_kernel.py"),
    "--iterations", "$Iterations",
    "--warmup", "$Warmup",
    "--flop-index", "$FlopIndex",
    "--out", $out
)

Push-Location $RepoRoot
try {
    if ($python.Count -eq 2) { & $python[0] $python[1] @args } else { & $python[0] @args }
    $code = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($code -ne 0) { throw "DeepPot fast-kernel benchmark exited with code $code" }
