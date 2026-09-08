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

Ryzen N=8 parallel scaling for the fast-v1 kernel, 62 tasks x 3,000 iterations:

- 15 workers: wall 15.044 s, 3,140,417 nodes/s;
- 23 workers: wall 9.321 s, 5,068,701 nodes/s;
- 31 workers: wall 8.568 s, 5,514,008 nodes/s.

**31 workers remains the winner** for this kernel and stays the production candidate.

The post-optimization N=8 profile shows the bottleneck has moved almost entirely into `_cfr_fast` itself. The evaluator is now a secondary cost. The largest remaining Python work is recursive CFR utility-vector construction, terminal utility materialization and reach/counterfactual-reach bookkeeping.

## Second-pass low-risk optimization

Before deciding whether to start the multi-day canonical master, one additional low-risk Python optimization is being tested in `src/deeppot/fast_solver_v2.py`.

Pot Fold's public decision tree is strictly sequential and each player acts at most once. Consequently, at the moment actor `i` acts, its own reach probability is always exactly 1.0. The reference implementation nevertheless carries a full reach vector and reconstructs counterfactual reach by multiplying all opponent entries at every public node.

Fast-v2 removes only that redundant representation:

- it carries the ordered product of prior action probabilities as one scalar;
- child counterfactual reach is `prior_path_reach * action_probability`;
- the current actor's linear-average reach multiplier remains exactly 1.0;
- the chance/RNG trajectory, public/private keys, regrets, policy sums, traversal order and terminal utility are unchanged.

This is not a solver-method change. Exact differential tests against the reference solver are mandatory and are included in CI.

The one-command Ryzen gate is:

```powershell
cd C:\DeepPot
git pull
powershell -ExecutionPolicy Bypass -File .\tools\benchmark_deeppot_fast_v2.ps1
```

It compares fast-v1 vs fast-v2 at N=2/5/8 and also performs a 31-worker N=8 parallel check.

## Decision rule after fast-v2

- If v2 gives a material additional gain and exact tests pass, v2 becomes the Python kernel candidate for continuous production.
- If the gain is small, stop Python micro-optimization and use fast-v1.
- Do **not** jump to a native C++ rewrite merely because it may be faster. With fast-v1 already at ~5.5 million N=8 decision nodes/s on 31 workers, native work is justified only if the projected end-to-end 1000-min-visit runtime remains operationally expensive after checkpoint/I/O measurement.
- Before the final long run, perform one end-to-end checkpoint/resume benchmark using the accepted kernel, because compute-only speedup does not include full-state serialization cost.

## Canonical master rule

The paused `C:\DeepPot\runs\continuous_master` remains a preserved pilot trajectory (`weighted mean visits = 1.90`, `target tasks = 0/12,285`). It is not the canonical V1.1 -> V1.2 -> V2 trajectory.

If fast-v1 or fast-v2 is accepted, start a fresh, source-locked optimized canonical master from iteration 1 under a new root. Do not mix the optimized kernel into the pilot states.

The final canonical trajectory must retain:

- every exact infoset;
- target minimum 1,000 real training visits per exact infoset;
- CFR+ and linear averaging;
- 31 workers unless a later accepted kernel materially changes scaling;
- resumable regrets, strategy sums, visit counts and RNG;
- arbitrary snapshots (V1.1/V1.2/V2) without consuming or restarting the master;
- optional continuation beyond 1,000 by raising only the stop target.
