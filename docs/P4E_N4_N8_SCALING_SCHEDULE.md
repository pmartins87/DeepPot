# P4E — predeclared N=4..8 scaling schedule

Reference date: 2026-09-07

This schedule is committed while the frozen N=3 P4E viability gate is still running. Its purpose is to prevent result-driven tuning if N=3 passes.

## Promotion condition

This schedule is used **only if both frozen N=3 P4E viability cases PASS** the unchanged gate:

- exact-policy coverage = 100%;
- every seat unilateral-gain 95% upper bound <= 0.030000 ante.

If either N=3 case fails, this schedule is not executed and P4E is BLOCKED.

## Fixed representative cases

For each N in 4..8 run exactly two already-defined textures:

- rainbow: `Ah 7d 2c`;
- monotone: `Ah 7h 2h`.

No additional texture is added inside P4E.

## Frozen scaling table

| N | CFR iterations / seed | CFR seeds | EG rounds | predictor samples / round | corrector samples / round | response learn | response holdout |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 4 | 250,000 | 3 | 64 | 50,000 | 50,000 | 250,000 | 250,000 |
| 5 | 100,000 | 3 | 64 | 25,000 | 25,000 | 100,000 | 100,000 |
| 6 | 100,000 | 3 | 64 | 25,000 | 25,000 | 100,000 | 100,000 |
| 7 | 100,000 | 3 | 64 | 25,000 | 25,000 | 100,000 | 100,000 |
| 8 | 100,000 | 3 | 64 | 25,000 | 25,000 | 100,000 | 100,000 |

The CFR and final response sample counts preserve the original frozen P4C representative-gate scaling. The extragradient scaling follows the previously predeclared multiway correction resource split: N=4 keeps the N=3 50k/50k chance blocks; N=5..8 use 25k/25k to keep the finite gate computationally bounded while retaining the same 64-round operator path.

## Parameters that do not scale

For every N=4..8 case:

- provisional rake = 2%, no cap;
- exact card representation, no strategic card abstraction;
- global suit isomorphism only;
- projected extragradient rounds = 64 exactly;
- predictor and corrector chance blocks are independent;
- maximum coordinate radius = `0.10 / sqrt(round)`;
- projection = coordinate clipping of `P(STAY)` to `[0,1]`;
- final threshold = every seat unilateral-gain 95% upper <= 0.030000 ante;
- no early stopping;
- no checkpoint selection;
- no texture-specific or player-count-specific radius tuning;
- no rerun with higher samples if a case fails.

## Finite decision rule

- If all ten N=4..8 representative cases PASS, P4E becomes the frozen multiway production method for N=3..8 under the provisional economy, and P4 calibration closes.
- If any one of the ten cases FAILS, P4E is BLOCKED for multiway production. We do not relax the gate or create a P4E sample/round ladder; the solver method changes again.

This file does not authorize execution before the N=3 promotion condition is satisfied.
