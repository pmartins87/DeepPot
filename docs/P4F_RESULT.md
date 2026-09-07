# P4F — N=3 primal-dual worst-seat viability result

Date: 2026-09-07

Workflow run: `34161823920`

Status: **BLOCKED**

## Frozen protocol

P4F was executed exactly as frozen before results in `docs/P4F_PRIMAL_DUAL_WORST_SEAT_METHOD_RESET.md`:

- N=3 only;
- representative rainbow `Ah 7d 2c` and monotone `Ah 7h 2h`;
- exact-state policy, no strategic card abstraction;
- warm start `CFR250k_x3 -> FP32x50k -> PED32x(BR50k+GRAD50k)`;
- 32 primal-dual mirror-prox rounds;
- predictor and corrector each used independent 50k BR-learning and 50k gradient blocks;
- primal radius `0.05/sqrt(round)`;
- dual radius `0.50/sqrt(round)`;
- original independent response gate: 250k learn + 250k holdout;
- PASS requires 100% intended coverage and every seat unilateral-gain 95% upper bound <= 0.030000 ante.

No early stopping, checkpoint selection, parameter sweep or threshold change was used.

## Final independent holdout results

| flop | seat 0 upper | seat 1 upper | seat 2 upper | result |
|---|---:|---:|---:|---|
| `Ah 7h 2h` monotone | 0.004295 | 0.010866 | 0.015436 | PASS |
| `Ah 7d 2c` rainbow | 0.015658 | 0.016334 | **0.039877** | **FAIL** |

Coverage was 100% in both cases.

For rainbow, the independent holdout unilateral-gain estimates were:

- seat 0: mean `0.0121801912`, upper 95% `0.0156579995`;
- seat 1: mean `0.0135065191`, upper 95% `0.0163337094`;
- seat 2: mean `0.0368945732`, upper 95% `0.0398774109`;
- total gain: mean `0.0625812834`, upper 95% `0.0679689165`.

The rainbow final BR STAY-state counts were `[637, 1428, 1508]`, with zero unreachable exact infosets for all three seats.

Final P4F dual seat weights were:

- rainbow: `[0.8150153415, 0.1659721016, 0.0190125570]`;
- monotone: `[0.5354549920, 0.4005954314, 0.0639495766]`.

## Diagnostic conclusion

P4F is not promoted to N=4..8. The frozen rainbow gate failed, so the method is **BLOCKED** and receives no extra P4F rounds, samples, alternate radii, checkpoint selection or relaxed threshold.

A specific estimator pathology was exposed by the run: during P4F optimization the independently sampled BR-learning and gradient blocks frequently produced negative estimated `seat_gaps`, although unilateral exploitability is non-negative by definition for an exact best response evaluated on the same underlying game distribution. The stochastic mismatch also drove the rainbow dual weights heavily toward seat 0 even though the untouched final holdout found seat 2 to be the worst exploitable seat.

This does not invalidate the independent response gate. It indicates that P4F's per-round independently sampled optimization objective is too noisy/misaligned for the exact rainbow state space at the frozen budget.

The next method reset must therefore change the estimator, not merely tune P4F. P4G uses one immutable common-random-number chance corpus throughout optimization so that each empirical BR is learned and evaluated on the same finite game. Final acceptance remains on the original independent split-sample response gate.
