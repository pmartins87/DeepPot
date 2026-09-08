# DeepPot continuous training — performance gate before canonical long run

Reference date: 2026-09-08

Status: **mandatory before declaring the 1000-visit continuous master canonical**

## Why this gate was added

The first resumable continuous run was started successfully with 31 workers, target `visit_count >= 1000` for every one of the 635,675,248 exact infosets, and 50,000-iteration atomic checkpoints. Immediately after startup, the user correctly recalled that the computational kernel itself had not yet received the same dedicated performance pass as the new persistence/resume infrastructure.

The pilot was paused safely at:

- `weighted mean visits = 1.90`;
- `task min-visit median = 0`;
- `target tasks = 0/12,285`;
- final console state `SAFE TO CLOSE`.

This is negligible progress versus the 1000-visit target, so it is preferable to optimize before spending multi-day compute.

The current `continuous_master` is therefore a **pilot trajectory**, not the canonical V1.1 -> V1.2 -> V2 master. It must remain preserved for traceability, but a materially faster mathematically equivalent implementation may start a fresh canonical master.

## Current-kernel Ryzen baseline

Representative canonical flop index 877, 2,000 iterations per N:

| N | Public scenarios | Wall | iter/s | decision nodes/s |
|---|---:|---:|---:|---:|
| 2 | 2 | 0.069 s | 28,992.86 | 57,986 |
| 5 | 30 | 0.602 s | 3,319.56 | 99,587 |
| 8 | 254 | 5.783 s | 345.87 | 87,850 |

The N=8 cProfile showed that the 7-card evaluator was not the dominant bottleneck. The expensive work was repeated Python public-tree/state/economy handling: terminal utility generation, immutable state transitions and infoset reconstruction.

## Fast exact Python kernel candidate

A mathematically equivalent candidate was implemented in `src/deeppot/fast_solver.py`.

It preserves:

- exact chance shuffle/RNG trajectory;
- exact flop-relative private-state index;
- exact public scenarios;
- exact FOLD-before-STAY traversal order;
- CFR+ regret updates;
- global linear-average weighting;
- terminal economy and ties;
- no abstraction or pruning.

It removes repeated hot-path work by precomputing the public tree and terminal constants, computing the hole-state ID once per player/deal, updating reach in place, and avoiding repeated immutable `PotFoldState` construction and scenario reconstruction.

Differential tests require exact equality of visit counts, regrets, strategy sums and resume trajectory. A BTN terminal-fold bug found by CI during development was fixed before acceptance; CI on commit `75f6dde1e72f64605efd59b20b3adb6ae5f46efc` passed.

### Ryzen A/B result — 5,000 iterations per implementation/N

| N | Reference | Fast | Speedup | Fast nodes/s |
|---|---:|---:|---:|---:|
| 2 | 0.172 s | 0.094 s | **1.84x** | 106,810 |
| 5 | 1.509 s | 0.402 s | **3.75x** | 372,860 |
| 8 | 13.385 s | 3.151 s | **4.25x** | 402,985 |

This is a material safe single-process speedup. N=8 dominates the exact state space, so the result is large enough to justify abandoning the pilot as the eventual canonical trajectory if the parallel/end-to-end gate also passes.

## What was optimized already

The Base-v1/continuous solver already had important optimizations:

- exact flop-relative hole-state IDs precomputed for all 1,176 raw hole pairs;
- final seven-card ranks computed once per player/deal and reused across public histories;
- direct 7-card evaluator;
- atomic resumable CFR state;
- frozen finite worker benchmark.

The fast candidate adds public-tree and repeated-state-work elimination without changing strategy semantics.

## Remaining performance gates

Before starting the canonical multi-day master:

1. benchmark the fast kernel under real Ryzen multiprocessing at worker candidates `15,23,31`;
2. profile the fast N=8 kernel after the first optimization pass;
3. re-evaluate whether a dense-array or native C++ kernel offers enough additional benefit to justify its implementation/validation cost;
4. if the final accepted kernel differs from the pilot implementation, start a fresh optimized canonical root rather than silently mixing source hashes into `continuous_master`;
5. verify exact interrupt/resume again using the final accepted kernel;
6. only then launch the 1000-min-visit trajectory.

The new one-command scaling/profile gate is:

```powershell
powershell -ExecutionPolicy Bypass -File C:\DeepPot\tools\benchmark_deeppot_fast_scaling.ps1
```

It does not modify the paused continuous pilot.

## Locked optimization rule

Performance work may change implementation, memory layout and execution language, but it may **not** change the strategy method:

- same exact state space;
- same 1,755 canonical flops;
- same 494 public scenarios;
- same FOLD/STAY game tree and payoffs;
- same provisional 2% uncapped economy unless separately corrected by evidence;
- CFR+;
- linear averaging with the true global iteration number;
- no strategic card abstraction/bucketing;
- no pruning that changes the solved game;
- reproducible fixed seed/configuration;
- resumable persistent regrets, strategy sums and visit counts.

## Canonical-master rule

Do not invest multi-day compute in the pilot master.

- **No material safe speedup found:** resume/promote the pilot.
- **Material safe speedup found:** preserve the pilot for traceability, start a fresh canonical optimized master from iteration 1, and use that one trajectory for V1.1 -> V1.2 -> V2 and later 1500/2000+ extensions.

The fast A/B already satisfies the single-process material-speedup gate. Parallel scaling and the second-pass optimization decision remain open.

## Safe pause instruction

For any active long run, press `Ctrl+C` exactly once and wait until the trainer prints `SAFE TO CLOSE`. Never kill the process or shut down Windows before that message.
