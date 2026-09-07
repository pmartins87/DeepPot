# P4G — frozen N=4..8 scaling protocol

Date frozen: 2026-09-07

Status at freeze: **P4G N=3 PASS; no P4G N=4..8 result observed**

This document freezes the one permitted N=4..8 scaling schedule required by `docs/P4G_FIXED_CORPUS_METHOD_RESET.md` before any N=4 result is observed.

## Method retained without strategic changes

Every mode keeps the same mathematical chain used by the successful N=3 P4G viability test:

`exact CFR consensus -> finite FP warm start -> finite PED warm start -> deterministic fixed-corpus smooth-worst-seat mirror-prox -> independent response gate`

No strategically lossy card abstraction is introduced. Exact global suit isomorphism remains the only state reduction.

The following parameters are unchanged for all N=4..8:

- CFR seeds: `1,2,3`;
- FP rounds: `32`;
- FP prior weight: `4`;
- PED rounds: `32`;
- PED initial coordinate step: `0.10/sqrt(round)`;
- P4G rounds: `32`;
- P4G corpus seed: `9802026`;
- P4G smooth-max beta: `100.0`;
- P4G coordinate radius: `0.05/sqrt(round)`;
- response-validator seed: `9302026`;
- provisional calibration rake: `2%`, uncapped;
- final PASS threshold: every seat unilateral-gain 95% CI upper `<= 0.030000 ante`;
- intended exact-state coverage: `1.000000`;
- no early stopping, parameter sweep, favorable checkpoint selection or post-result tuning.

## Frozen finite scaling table

The only scaled quantity inside the optimizer is the per-round/corpus chance-sample budget. The public tree grows exponentially with player count, so retaining the N=3 50k corpus unchanged through N=8 would make the one-shot finite gate impractical on the hosted runner. The schedule below was fixed before seeing any N=4 result.

| N | CFR iterations/seed | FP samples/round | PED BR samples/round | PED gradient samples/round | P4G fixed corpus | response learn | response holdout |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 4 | 250,000 | 50,000 | 50,000 | 50,000 | 50,000 | 250,000 | 250,000 |
| 5 | 100,000 | 40,000 | 40,000 | 40,000 | 40,000 | 100,000 | 100,000 |
| 6 | 100,000 | 30,000 | 30,000 | 30,000 | 30,000 | 100,000 | 100,000 |
| 7 | 100,000 | 20,000 | 20,000 | 20,000 | 20,000 | 100,000 | 100,000 |
| 8 | 100,000 | 10,000 | 10,000 | 10,000 | 10,000 | 100,000 | 100,000 |

N=4 retains the full N=3 optimization sample budget. N=5..8 reduce the finite optimizer sample budget monotonically to compensate for the rapidly expanding public tree while leaving rounds, objective, state representation, response threshold and independent acceptance design unchanged.

The response sample schedule deliberately reuses the already-frozen multiway P4C representative-gate convention: N=4 receives 250k learn + 250k holdout; N=5..8 receive 100k + 100k. Lower response samples produce wider confidence intervals and therefore do not make the `<=0.03` upper-bound gate easier.

## Representative cases

Exactly ten cases are allowed:

- N=4 rainbow `Ah 7d 2c`;
- N=4 monotone `Ah 7h 2h`;
- N=5 rainbow `Ah 7d 2c`;
- N=5 monotone `Ah 7h 2h`;
- N=6 rainbow `Ah 7d 2c`;
- N=6 monotone `Ah 7h 2h`;
- N=7 rainbow `Ah 7d 2c`;
- N=7 monotone `Ah 7h 2h`;
- N=8 rainbow `Ah 7d 2c`;
- N=8 monotone `Ah 7h 2h`.

## Decision rule

For a given player count N, P4G is accepted for that mode only if **both** representative textures have 100% intended policy coverage and every seat's unilateral-gain 95% CI upper is at most `0.030000 ante`.

If either texture fails for a player count, P4G is BLOCKED for that N. We do not add more P4G rounds, enlarge that N's corpus, alter beta/radius, increase its warm-start samples, select an earlier checkpoint or relax the threshold after seeing the result. P4 remains open for the failed mode(s) and the solver method changes there.

If all ten cases pass, P4G becomes the frozen provisional-economy production method for N=3..8 and multiway P4 closes.
