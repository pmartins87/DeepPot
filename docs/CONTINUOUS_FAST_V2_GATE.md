# DeepPot continuous training — fast-kernel v2 gate

Reference date: 2026-09-08

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

## Fast-v2 accepted as the Python production candidate

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

This is an additional ~13% N=8 gain on top of fast-v1 and is material because N=8 dominates the exact state space. Fast-v2 is therefore the accepted Python kernel candidate for the canonical continuous master.

## Canonical fast-v2 continuous infrastructure

The paused pilot root remains preserved:

`C:\DeepPot\runs\continuous_master`

It stopped safely at weighted mean visits 1.90 and must not be mixed with the optimized trajectory.

The optimized canonical root is intentionally separate:

`C:\DeepPot\runs\continuous_master_fast_v2`

New source-locked components:

- `src/deeppot/continuous_training_fast_v2.py` — persistent fast-v2 state, atomic checkpoint, exact RNG resume and visit statistics;
- `src/deeppot/continuous_runner_fast_v2.py` — hardened 31-worker interruptible runner;
- `tools/run_deeppot_continuous_fast_v2.ps1` — canonical one-command launcher;
- `tests/test_continuous_fast_v2_resume.py` — persistent checkpoint/load/continue exactness test.

The original pilot modules and root remain available for traceability.

## Final end-to-end gate before the multi-day run

Compute-only benchmarks do not include loading, dense-state scan, serialization, fsync and atomic file replacement. Therefore one final short Ryzen gate is mandatory before launching the canonical 1000-min-visit master:

```powershell
cd C:\DeepPot
git pull
powershell -ExecutionPolicy Bypass -File .\tools\benchmark_deeppot_continuous_fast_v2_e2e.ps1
```

This benchmark uses 31 representative N=8 flop tasks and the real canonical 50,000-iteration checkpoint size. It executes:

1. a fresh 50k wave including state/greedy/summary checkpoint;
2. a resumed 50k wave including persisted CFR/RNG load and atomic replacement checkpoint.

It reports actual end-to-end nodes/s, visit-min distribution after 100k iterations and a rough runtime projection to min_visit ~1000. It writes only under:

`C:\DeepPot\runs\kernel_benchmark_continuous_fast_v2_e2e`

and does not touch either continuous master.

## C++ decision rule

Do **not** implement a native C++ rewrite by default. Fast-v2 already reaches ~6.42 million N=8 decision nodes/s in the short 31-worker scaling test. Native work is justified only if the end-to-end gate shows that the true 1000-min-visit runtime remains operationally expensive enough to outweigh implementation and equivalence-validation cost.

If the E2E runtime is reasonable, stop performance work and launch fast-v2. This follows the project rule: maximize poker quality and useful compute, not engineering complexity for its own sake.

## Canonical master rules

The final canonical trajectory must retain:

- all 635,675,248 exact infosets;
- all 1,755 canonical flops and 494 public scenarios;
- target minimum 1,000 real training visits per exact infoset;
- CFR+ and global linear averaging;
- 31 workers;
- no strategic abstraction or pruning;
- persistent regrets, strategy sums, visit counts and RNG;
- graceful Ctrl+C pause and exact resume;
- arbitrary V1.1/V1.2/V2 snapshots without consuming or restarting the master;
- optional continuation beyond 1,000 by changing only the stop target.
