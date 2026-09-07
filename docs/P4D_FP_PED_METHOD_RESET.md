# P4D — finite FP-PED method reset after P4C BLOCKED

## Why this phase exists

P4C is closed as **BLOCKED** for the current multiway method.

The original frozen exact-state CFR+ candidates failed the unilateral-response gate on all 12 representative N/texture cases (N=3..8; rainbow and monotone). The single correction permitted by the roadmap was then applied to the already-failed N=3..6 cases: 32 rounds of finite multiplayer fictitious-response averaging, followed by one rerun of the unchanged response gate. All eight corrected N=3..6 cases still failed.

Corrected worst-seat unilateral-gain 95% upper bounds were:

| N | rainbow | monotone | frozen threshold |
|---:|---:|---:|---:|
| 3 | 0.070115 | 0.031408 | <= 0.030000 |
| 4 | 0.131516 | 0.061585 | <= 0.030000 |
| 5 | 0.238271 | 0.149504 | <= 0.030000 |
| 6 | 0.310460 | 0.204696 | <= 0.030000 |

Coverage remained 100% in these corrected cases. The failure is therefore response quality, not missing-state coverage.

Per the finite-execution rule, we do **not** add more CFR iterations, more fictitious-response rounds, a new alpha schedule, or a relaxed threshold. We also do not spend compute applying the already-disproven P4C correction to N=7/8. The method changes.

## New method

P4D uses a finite exact-state **FP-PED** path:

1. exact CFR consensus warm start;
2. the already-frozen 32-round fictitious-response average as the FP warm start;
3. stochastic Projected Exploitability Descent (PED) on the aggregate unilateral-deviation objective;
4. the original independent split-sample response gate.

For DeepPot, every player acts at most once. Therefore each player's sequence-form feasibility constraints reduce to independent two-action simplexes at its exact information sets. PED projection is consequently exact and local: every updated `P(STAY)` is projected to `[0,1]`, with `P(FOLD)=1-P(STAY)`.

No card abstraction is introduced. Global suit isomorphism is the only symmetry reduction.

## Frozen N=3 viability gate

Before any N=4..8 PED run, execute exactly two viability cases:

- N=3, `Ah 7d 2c` (rainbow);
- N=3, `Ah 7h 2h` (monotone).

Both use the same fixed schedule:

- initial CFR candidate: 250k x 3 seeds;
- FP warm start: 32 rounds x 50k chance samples, prior weight 4;
- PED rounds: exactly **32**;
- per PED round BR-learning block: **50,000** chance samples;
- per PED round gradient block: **50,000 independent** chance samples;
- PED projected step: normalized subgradient with maximum coordinate movement `0.10 / sqrt(round)`;
- deterministic seed base: `9_502_026`;
- provisional rake: 2%, unchanged;
- final gate: exactly 250k BR-learning + 250k independent holdout samples;
- PASS: every seat unilateral-gain 95% upper bound <= 0.03 ante;
- exact policy coverage must remain 100%.

There is no early stopping, texture-specific tuning, checkpoint selection, parameter sweep, or threshold relaxation.

### Viability decision

- If **both** N=3 textures PASS, the same FP-PED method is promoted to N=4..8. N=4 uses 50k BR + 50k gradient samples per PED round; N=5..8 use 25k + 25k per PED round, with the same 32 rounds and step schedule. Each mode still receives only its original representative response gate.
- If **either** N=3 texture fails, P4D is **BLOCKED**. We do not add PED rounds or tune the step size after seeing the result; the solver method must change again.

## Implementation note

The PED gradient is computed directly on the exact public FOLD/STAY tree. For each sampled chance deal, the implementation evaluates the profile once and one unilateral-BR value/reach recursion per player. This gives O(N * public-tree-nodes) work per deal rather than constructing N full N-player utility tensors. The gradient minimizes the sum of unilateral deviation gains while preserving the exact dense infoset key space.