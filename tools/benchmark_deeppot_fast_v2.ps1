param(
    [int]$FlopIndex = 877,
    [int]$Iterations = 5000,
    [int]$ParallelIterations = 3000,
    [int]$Tasks = 62,
    [int]$Workers = 31
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $repo 'src'

python (Join-Path $PSScriptRoot 'benchmark_deeppot_fast_v2.py') `
    --flop-index $FlopIndex `
    --iterations $Iterations `
    --parallel-iterations $ParallelIterations `
    --tasks $Tasks `
    --workers $Workers `
    --out (Join-Path $repo 'runs\kernel_benchmark_fast_v2\v2.json')

if ($LASTEXITCODE -ne 0) {
    throw "DeepPot fast-v2 benchmark failed with exit code $LASTEXITCODE"
}
