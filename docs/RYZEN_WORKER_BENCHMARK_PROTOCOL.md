# DeepPot — finite Ryzen worker-count benchmark

Date: 2026-09-08

## Purpose

Choose the worker count for the official DeepPot Ryzen production run without guessing and without creating a tuning ladder.

This is a **performance-only calibration**. It does not alter strategy, solver mathematics, EV/CI rules, rake assumptions, state representation, or release criteria.

## Why this measurement exists

The official DeepKK Ryzen configuration used 31 workers on a 32-logical-processor host. DeepPot should preserve that result as the primary reference, but its multiprocessing granularity is different: DeepPot distributes independent flop jobs across processes. Therefore one finite local measurement is allowed before the long production run.

## Frozen protocol

On the target Ryzen host:

1. detect logical processor count `L`;
2. benchmark exactly three worker levels derived before observing results:
   - `floor(L/2)-1`;
   - `floor(3L/4)-1`;
   - `L-1`;
3. on a 32-logical-processor Ryzen these are exactly **15, 23, 31**;
4. use N=8, the heaviest supported public tree;
5. use exactly 64 canonical flops spread evenly across all 1,755 canonical flop IDs;
6. per flop run exactly 3,000 CFR+ iterations plus 3,000 samples through the exact compact EV-audit path;
7. each candidate is executed exactly once on the same fixed workload and seed 123;
8. choose the candidate with the smallest wall-clock time; exact tie goes to the lower worker count;
9. write the winner to `runs/worker_benchmark/selected_workers.txt` and the full evidence to `worker_benchmark.json`.

The reduced benchmark solve may not visit every infoset. Missing benchmark-only policy entries are filled with neutral 50/50 solely so the production EV-audit code path and memory footprint can be timed. The **official trainer does not use that fill** and still requires complete solver coverage.

## No tuning ladder

There is no second candidate search after observing the result. Do not add 16/20/24/28/30/32, repeat runs, or optimize based on small differences unless a concrete benchmark implementation or machine-state fault invalidates the measurement.

The official trainer reads the selected worker file automatically when `-Workers` is not specified. If the benchmark file does not exist, the fallback is `logical_processors - 1`, preserving the DeepKK 31-worker precedent on the known 32-thread Ryzen.

## Command

From the repository root in PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\benchmark_deeppot_workers.ps1
```

After completion, the production command remains:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_deeppot_ryzen.ps1
```
