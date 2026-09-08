# DeepPot continuous training — performance gate before canonical long run

Reference date: 2026-09-08

Status: **mandatory before declaring the 1000-visit continuous master canonical**

## Why this gate was added

The first resumable continuous run was started successfully with 31 workers, target `visit_count >= 1000` for every one of the 635,675,248 exact infosets, and 50,000-iteration atomic checkpoints. Immediately after startup, the user correctly recalled that the computational kernel itself had not yet received the same dedicated performance pass as the new persistence/resume infrastructure.

At the moment the issue was noticed the console reported approximately:

`chunks=25 target_tasks=0/12,285 mean_visits=0.02 task_min_median=0`

This is negligible progress versus the 1000-visit target, so it is preferable to pause now and benchmark/optimize rather than spend many days on an avoidably slow implementation.

The current `continuous_master` is therefore a **pilot trajectory**, not yet the canonical V1.1->V1.2->V2 master. It may be discarded if a materially faster mathematically equivalent implementation is accepted.

## What was optimized already

The existing Base-v1/continuous Python solver already includes important optimizations that do not change strategy semantics:

- exact flop-relative hole-state IDs are precomputed for all 1,176 raw hole pairs;
- final seven-card ranks are computed once per player/deal and reused across terminal public histories;
- the 7-card evaluator is direct rather than enumerating all 21 five-card subsets;
- multiprocessing uses the frozen 31-worker Ryzen result;
- continuous state is checkpointed atomically and can resume exact regrets/strategy sums/visits/RNG.

Those are real optimizations, but they are not a full hot-path optimization pass.

## Remaining hot-path opportunities

The current kernel still performs substantial Python-level work inside every sampled deal and every public-tree node:

1. full Python recursive CFR traversal;
2. repeated immutable `PotFoldState` construction and list/tuple copying in `apply()`;
3. dictionary lookup plus Python `InfoNode` objects despite dense integer infoset keys;
4. Python `HandRank`, rank-count and suit-list object creation in the evaluator;
5. a full 49-card Python shuffle even though only `2*N + 2` cards are consumed;
6. Python tuple/list action-utility and reach allocations at each CFR node;
7. full-state serialization/stat scanning at every completed checkpoint chunk.

For N=8 the public decision tree contains 254 decision scenarios per sampled deal, so Python per-node overhead is multiplied heavily.

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

## Optimization candidates

The preferred order is:

1. benchmark/profile the current Python kernel on the actual Ryzen;
2. remove avoidable Python allocations and use precomputed public-tree structure/dense state where this produces a material win;
3. benchmark a compiled/native exact CFR hot path (C++ is preferred because the Ryzen already has the validated VS2022/v143 toolchain) if Python optimization is not enough;
4. accept an optimized kernel only after differential tests show equivalent game/state mapping and numerically/policy-consistent CFR behavior on finite deterministic tests;
5. benchmark worker count again only if the per-worker memory/compute profile changes materially; otherwise retain 31.

The goal is wall-clock reduction only. This is not permission to reinvent the solver methodology.

## Canonical-master rule

Do not invest multi-day compute in the pilot master. Pause gracefully, benchmark, and then choose one of two outcomes:

- **No material safe speedup found:** resume the existing pilot and promote it to canonical continuous master.
- **Material safe speedup found:** preserve the pilot for traceability, start a fresh canonical optimized master from iteration 1, and use that single trajectory for V1.1 -> V1.2 -> V2 and any later 1500/2000+ extension.

Because the pilot was caught at roughly `mean_visits=0.02`, restarting it would discard an immaterial fraction of the final target.

## Safe pause instruction

In the active training PowerShell, press `Ctrl+C` exactly once and wait until the trainer prints `SAFE TO CLOSE`. Do not kill the process or shut down Windows before that message.
