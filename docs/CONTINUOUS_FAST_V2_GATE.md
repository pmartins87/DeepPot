# DeepPot continuous training — fast-kernel v2 gate

Reference date: 2026-09-08

Status: **CLOSED / FAST V2 APPROVED FOR CANONICAL DEEP TRAINING**

## Accepted facts from the Ryzen benchmarks

The original exact Python CFR kernel baseline on representative flop 877 was:

- N=2: 28,992.86 iter/s, 57,986 decision nodes/s;
- N=5: 3,319.56 iter/s, 99,587 decision nodes/s;
- N=8: 345.87 iter/s, 87,850 decision nodes/s.

The first exact fast Python candidate (`src/deeppot/fast_solver.py`) preserved the exact state space, exact chance/RNG trajectory, CFR+, global linear averaging, FOLD-before-STAY traversal, terminal economy and no abstraction. Differential tests compare visit counts, regrets, strategy sums and resume trajectory against the reference solver.

Ryzen single-process A/B at 5,000 iterations:

- N=2: 1.84x speedup;
- N=5: 3.75x speedup;
- N=8: 4.25x speedup.

Ryzen N=8 parallel scaling for fast-v1, 62 tasks x 3,000 iterations:

- 15 workers: wall 15.044 s, 3,140,417 nodes/s;
- 23 workers: wall 9.321 s, 5,068,701 nodes/s;
- 31 workers: wall 8.568 s, 5,514,008 nodes/s.

**31 workers remains the winner.**

## Fast-v2 accepted as the Python production kernel

`src/deeppot/fast_solver_v2.py` removes only redundant reach-vector bookkeeping from the strictly sequential one-decision-per-player Pot Fold tree. It carries the ordered product of prior action probabilities as one scalar. The chance trajectory, infoset keys, FOLD-before-STAY traversal, CFR+ regrets, global linear averaging and terminal utilities remain unchanged.

CI differential tests against the original reference solver require exact equality of:

- visit counts;
- regrets;
- strategy sums;
- RNG state;
- resume trajectory.

Those tests pass.

### Ryzen fast-v1 -> fast-v2 A/B

Representative flop 877, 5,000 iterations per implementation/N:

| N | fast-v1 | fast-v2 | Additional speedup | fast-v2 nodes/s |
|---|---:|---:|---:|---:|
| 2 | 0.090 s | 0.089 s | 1.02x | 112,654 |
| 5 | 0.390 s | 0.363 s | 1.07x | 412,853 |
| 8 | 2.869 s | 2.532 s | **1.13x** | **501,618** |

Fast-v2 31-worker N=8 parallel check, 62 tasks:

- wall: **7.354 s**;
- aggregate throughput: **6,423,910 decision nodes/s**;
- task mean: 2.956 s;
- task max: 3.027 s.

Fast-v2 is therefore the accepted kernel for the canonical continuous master.

## Final end-to-end Ryzen gate — PASS

Canonical E2E benchmark:

- workers: 31;
- representative tasks: 31 N=8 flops;
- canonical chunk: 50,000 iterations;
- wave 1: fresh train + atomic state/greedy/summary checkpoint;
- wave 2: load persisted CFR/RNG + continue + atomic replacement checkpoint.

Measured result:

### Fresh 50k wave

- wall: **48.138 s**;
- effective throughput: **8,178,639 decision nodes/s**;
- visit-min across the 31 N=8 tasks: **23 / 23 / 26** (min/median/max);
- median visit mean: **69.35**;
- persistent state written: **184.7 MiB**.

### Resumed +50k wave

- wall: **50.284 s**;
- effective throughput including load/checkpoint: **7,829,525 decision nodes/s**;
- visit-min across the 31 N=8 tasks: **54 / 55 / 60** (min/median/max);
- median visit mean: **138.70**;
- persistent state: **184.7 MiB**.

### Projection to the 1,000-minimum gate

From measured visit minima after 100,000 iterations:

- representative median projection: **1,818,182 iterations**;
- conservative representative projection from the worst of the 31 N=8 flops: **1,851,852 iterations**;
- rough all-N/all-flop compute projection using resumed E2E throughput: **~57.0 hours**.

This projection is only planning guidance. The canonical trainer does **not** stop by elapsed time or a hard iteration count. It stops only when every exact infoset has measured `visit_count >= 1000`.

## Engineering decision after the E2E gate

The E2E runtime is reasonable for the project objective. Therefore:

- **do not implement C++ now**;
- stop performance micro-optimization;
- launch the canonical fast-v2 trajectory from iteration 1;
- preserve the old `runs\\continuous_master` pilot untouched;
- use only `runs\\continuous_master_fast_v2` for the canonical V1.1 -> V1.2 -> V2 lineage;
- keep 31 workers and 50,000-iteration atomic chunks;
- continue beyond 1,000 later, if desired, by raising only `TargetMinVisits`; do not restart the trajectory.

The decision prioritizes poker-training depth and useful compute over engineering complexity that is no longer justified by expected wall-clock savings.

## Canonical continuous infrastructure

Paused pilot root, preserved for traceability:

`C:\\DeepPot\\runs\\continuous_master`

Canonical optimized root:

`C:\\DeepPot\\runs\\continuous_master_fast_v2`

Canonical launcher:

```powershell
powershell -ExecutionPolicy Bypass -File C:\\DeepPot\\tools\\run_deeppot_continuous_fast_v2.ps1
```

Canonical status helper:

```powershell
powershell -ExecutionPolicy Bypass -File C:\\DeepPot\\tools\\status_deeppot_continuous_fast_v2.ps1
```

Canonical snapshot helper:

```powershell
powershell -ExecutionPolicy Bypass -File C:\\DeepPot\\tools\\snapshot_deeppot_continuous_fast_v2.ps1 -Name V1.1
```

## Canonical master rules

The canonical trajectory must retain:

- all 635,675,248 exact infosets;
- all 1,755 canonical flops and 494 public scenarios;
- target minimum 1,000 real training visits per exact infoset;
- CFR+ and global linear averaging;
- 31 workers;
- no strategic abstraction or pruning;
- persistent regrets, strategy sums, visit counts and RNG;
- graceful Ctrl+C pause and exact resume;
- arbitrary V1.1/V1.2/V2 snapshots without consuming or restarting the master;
- no mandatory global EV/CI audit; targeted audit remains available;
- optional continuation beyond 1,000 by changing only the stop target.

## Source-lock rule once canonical training starts

After the canonical root has been created, do not alter mathematical training source files on that Ryzen trajectory. Documentation-only repository updates are harmless, but any change to files covered by the training source hash must not be mixed into the active master. If mathematical code ever must change, pause safely and evaluate migration explicitly rather than silently resuming incompatible state.
