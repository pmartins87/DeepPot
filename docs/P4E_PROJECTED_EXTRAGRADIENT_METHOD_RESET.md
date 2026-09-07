# P4E — exact-state projected Nash extragradient method reset

## Why P4E exists

P4C (chance-sampled CFR+ plus the single finite fictitious-response correction) failed the frozen multiway unilateral-response gate. P4D then changed the objective to sampled Projected Exploitability Descent (PED). In the frozen N=3 viability test, monotone `Ah 7h 2h` passed but max-state rainbow `Ah 7d 2c` failed because seat 2 had unilateral-gain 95% upper = 0.039123 ante against the unchanged 0.030000 threshold.

P4D is therefore BLOCKED. P4E is a **method reset**, not another P4D parameter rung.

## Structural change

P4E does not minimize the derivative of aggregate exploitability. It directly solves the local Nash best-response conditions.

For every exact infoset `I`, define

`A(I) = E[u(STAY) - u(FOLD) | I, current opponents]`.

Because a Pot-Fold player acts at most once, that player's action-value difference at `I` does not depend on its own probability at `I`. A Nash policy must satisfy the binary complementarity condition:

- `p_stay(I) = 0` only if `A(I) <= 0`;
- `p_stay(I) = 1` only if `A(I) >= 0`;
- `0 < p_stay(I) < 1` only if `A(I) = 0`.

P4E applies a stochastic **projected extragradient** to this exact-state action-advantage operator. The predictor is built from an independent chance block at the current policy. The corrector recomputes advantages at the predictor policy on a second independent chance block and updates from the original policy. This targets the Nash fixed-point/variational-inequality residual directly rather than the P4D aggregate-deviation objective.

No strategic card abstraction is introduced. Only exact global suit isomorphism remains.

## Frozen finite N=3 viability protocol

This file is committed before P4E gate results are observed.

Run exactly two cases:

1. N=3 `Ah 7d 2c` (max-state rainbow and the P4D failure);
2. N=3 `Ah 7h 2h` (low-state monotone regression guard).

For each case:

- warm start: the same frozen `250k x 3` exact CFR consensus used by P4C/P4D;
- P4E rounds: **64 exactly**;
- predictor advantage samples/round: **50,000**;
- corrector advantage samples/round: **50,000**, independent from predictor;
- normalized maximum coordinate radius: **`0.10 / sqrt(round)`**;
- projection: exact coordinate clipping of `P(STAY)` to `[0,1]`;
- no early stopping and no checkpoint selection;
- final validator: the existing independent `250k learn + 250k holdout` unilateral-response gate;
- provisional economy: 2% rake, no cap, exactly as earlier P4 calibration.

### Unchanged PASS gate

For both N=3 cases:

- exact-policy coverage = 100%;
- every seat unilateral-gain 95% upper bound <= **0.030000 ante**.

The external response validator is not used to select an intermediate round.

## Finite branching rule

- If both N=3 cases PASS, P4E is promoted to N=4..8 with one predeclared scaling schedule before those runs.
- If either N=3 case FAILS, P4E is BLOCKED. We do **not** add rounds, alter the radius, increase sample counts, choose an earlier checkpoint or relax the 0.03 threshold. The next action is another solver-method change.

This preserves the project rule that every validation path is finite.