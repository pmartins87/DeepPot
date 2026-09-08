# DeepPot Status

Reference date: 2026-09-08

## Current direction

DeepPot has two deliberately separate tracks:

1. **Base v1 frozen / live operational testing** — already solved, compiled and running on the i5 through OpenHoldem; never overwrite it.
2. **Continuous deep CFR track** — runs on the Ryzen 9, starts a new resumable trajectory and targets at least **1,000 actual training visits for every exact infoset**.

The DeepKK-parity principle remains authoritative: preserve the exact game/scenario space, CFR+ and linear averaging. The deeper track changes training depth/checkpointing and implementation efficiency, not the strategic abstraction.

Authoritative documents:

- `docs/CONTINUOUS_TRAINING_V2.md`;
- `docs/CONTINUOUS_PERFORMANCE_GATE.md`;
- `docs/CONTINUOUS_FAST_V2_GATE.md`;
- `docs/CONTINUOUS_TRAINING_POST1000.md`.

## Base v1 mathematical source — COMPLETE / FROZEN

Official Ryzen run:

- N=2..8;
- all 1,755 canonical flops per mode;
- 494 public scenarios;
- 635,675,248 exact infosets;
- seed 123;
- CFR+ + linear average;
- 20,000 solver iterations per flop;
- 50,000 independent EV-audit samples per flop;
- audit minimum effective visits 25;
- provisional 2% uncapped rake;
- 31 workers;
- elapsed **22,598.7 s = 6.28 h**.

Source run manifest SHA256:

`a1a05a6988ea937ec82a576c7cbf6c7ff2b03ceaa089e448dc3b4756322d5e14`

P5 freeze manifest:

`C:\DeepPot\runs\p5_freeze\P5_FREEZE_MANIFEST.json`

SHA256:

`4d4077796ce81ec4d74a99818d69cc999221ad77c973c7d6fe7d4102d1a43a8a`

Never alter/delete:

- `runs\deepkk_parity_full`;
- `runs\deeppot_runtime`;
- `runs\p5_freeze`.

## Base v1 depth/audit interpretation

The full CFR tree traversal generated about 17.34 billion node visits, but across the 635.7 million exact infosets this is only about **27.28 training visits per infoset on average**.

Audit outcome:

| N | infosets | low coverage | confident | final STAY |
|---:|---:|---:|---:|---:|
| 2 | 2,573,584 | 0.1602% | 66.3441% | 80.4089% |
| 3 | 7,720,752 | 10.3988% | 52.2670% | 64.6348% |
| 4 | 18,015,088 | 32.7921% | 37.4199% | 53.3870% |
| 5 | 38,603,760 | 50.9822% | 26.5572% | 45.2988% |
| 6 | 79,781,104 | 70.7244% | 15.7645% | 39.7704% |
| 7 | 162,135,792 | 84.2742% | 8.6108% | 36.7355% |
| 8 | 326,845,168 | 91.7877% | 4.6051% | 36.7748% |

Totals:

- covered at least once in audit: 100.0000%;
- low audit coverage: **81.7182%**;
- confident: **10.1193% of all states / 55.3521% of adequately covered states**;
- final STAY: **38.6442%**;
- confident EV overrides: **8,307,288**.

Low audit coverage does not mean missing strategy: every supported state has a final action, with inconclusive states using the greedy linear-average CFR action. It does mean Base v1 is materially shallower per exact state than DeepKK.

DeepKK official comparison: 20,000 iterations x 24,000 deals/iteration = 480 million deals per mode, and its official EV audit used `min_visits=5000`. The 25-visit value existed only in the quick preset.

## P7 mathematical -> runtime equivalence — PASS

`C:\DeepPot\runs\p7_equivalence\P7_EQUIVALENCE_RESULT.json`

- structurally resolvable: **635,675,248 / 635,675,248**;
- unknown supported keys: **0**;
- action bit mismatches: **0**;
- index metadata mismatches: **0**;
- source/runtime final SHA256 identical for N2..N8.

## OpenHoldem live runtime — TESTING ON i5

Machine roles are the same pattern used for DeepKK:

- **Ryzen 9:** solver/build/deep training;
- **i5:** KKPoker + OpenHoldem live tests.

Implemented runtime:

- one `dll$deeppot_action` contract for all 494 scenarios;
- exact bit lookup; no live solver/equity calculation;
- exact flop/hole canonicalization;
- lossless N2..N8 final bitsets;
- fail-closed return 0;
- deterministic HIT/MISS logs.

Live corrections already made:

- OpenHoldem/PokerEval suit encoding corrected from H=0,D=1,C=2,S=3 to DeepPot C=0,D=1,H=2,S=3 via mapping `[2,1,0,3]`;
- prior FOLD/STAY reconstruction corrected so a prior actor missing from `playersplayingbits` is interpreted as FOLD even when KKPoker/OpenHoldem does not preserve the corresponding `foldbits2` bit; contradictory playing+folded state still fails closed.

Live tests showed coherent HIT decisions overall. Suspicious individual actions remain eligible for targeted mathematical inspection. `negative potcommon`/some scraper warnings remain tablemap concerns and are separate from exact DeepPot lookup when required state symbols are valid.

## Continuous deep CFR track — RESUMABLE INFRASTRUCTURE COMPLETE

Target:

> **every exact infoset `visit_count >= 1000`**.

This is a real depth target, not “run for 15 days”. `1000` is a pragmatic first target, not a theorem. If the policy remains materially unstable at 1,000, the same master continues deeper by raising only the stop target.

Core properties:

- persistent atomic per-task state with regrets, strategy sums, visit counts, completed iterations and RNG;
- exact source/config provenance lock;
- 12,285 tasks (N2..N8 × 1,755 flops), interleaved by flop;
- default 50,000-iteration checkpoint chunks;
- graceful Ctrl+C pause and `SAFE TO CLOSE`;
- exact resume;
- arbitrary-time snapshot export;
- cross-snapshot exact action-bit stability comparison;
- no mandatory global EV/CI audit on the deep track; targeted audit remains available.

Persistent-state payload estimate: **~21.31 GiB** plus metadata/snapshots. Initial free-space safety floor is 30 GiB; resumed sessions use a 2 GiB working-space floor.

## Pilot continuous master — PAUSED / PRESERVED

The first resumable master used the original Python kernel and was intentionally paused before investing multi-day compute.

Root:

`C:\DeepPot\runs\continuous_master`

Safe final state:

- `weighted mean visits = 1.90`;
- `task min-visit median = 0`;
- `target tasks = 0/12,285`;
- console ended with `SAFE TO CLOSE`.

This root is a pilot only and must not be mixed with the optimized trajectory.

## Performance optimization — FAST V2 ACCEPTED

Original representative N=8 kernel baseline:

- **87,850 decision nodes/s** single process.

Fast-v1:

- **4.25x** N=8 single-process speedup vs reference;
- 31-worker scaling winner: **5,514,008 nodes/s**.

Fast-v2 (`FastChanceSampledCFRV2`) removes redundant reach-vector bookkeeping while preserving the exact strategy method. Differential CI requires exact equality of visit counts, regrets, strategy sums, RNG state and resume trajectory against the reference solver.

Ryzen fast-v1 -> fast-v2 A/B:

| N | v1 | v2 | additional speedup | v2 nodes/s |
|---|---:|---:|---:|---:|
| 2 | 0.090 s | 0.089 s | 1.02x | 112,654 |
| 5 | 0.390 s | 0.363 s | 1.07x | 412,853 |
| 8 | 2.869 s | 2.532 s | **1.13x** | **501,618** |

31-worker fast-v2 N=8 check:

- wall **7.354 s**;
- aggregate **6,423,910 nodes/s**;
- task mean 2.956 s;
- task max 3.027 s.

**Decision:** fast-v2 is the accepted Python kernel candidate. 31 workers remains frozen.

## Canonical optimized master — NOT STARTED YET

Canonical root reserved for the optimized trajectory:

`C:\DeepPot\runs\continuous_master_fast_v2`

Launcher:

`tools\run_deeppot_continuous_fast_v2.ps1`

The optimized master starts from iteration 1 and remains the single trajectory for V1.1 -> V1.2 -> V2 and any later 1500/2000+ continuation.

### Snapshot plan

Suggested labels are operational conveniences only:

- `V1.1` after an early useful amount of training;
- `V1.2` later in the same trajectory;
- `V2` when all exact infosets reach the configured 1,000 minimum.

The former 5/10/15-day idea is not a quality gate and may become obsolete because the optimized kernel is much faster.

## Final gate before canonical launch

One short end-to-end Ryzen benchmark remains. It measures real compute + checkpoint/load/serialization cost with the accepted fast-v2 kernel and real 50,000-iteration chunk size:

```powershell
cd C:\DeepPot
git pull
powershell -ExecutionPolicy Bypass -File .\tools\benchmark_deeppot_continuous_fast_v2_e2e.ps1
```

It uses 31 representative N=8 tasks, performs a fresh 50k wave and a resumed 50k wave, reports effective end-to-end nodes/s and visit-min distribution, and writes only under:

`runs\kernel_benchmark_continuous_fast_v2_e2e`

It does **not** touch the paused pilot or the reserved canonical root.

### Native C++ policy

Do not build a C++ kernel by default. Only do so if the final E2E benchmark shows that the 1,000-min-visit runtime remains expensive enough to justify the implementation/equivalence cost. Otherwise stop optimization and launch fast-v2.
