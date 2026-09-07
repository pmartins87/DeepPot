# P4G — deterministic fixed-corpus worst-seat method reset

Date frozen: 2026-09-07

Status at freeze: **NO P4G viability result observed**

## Why P4G exists

P4F failed the N=3 rainbow viability gate. Its internal independently sampled BR-learning and gradient blocks also produced negative estimated unilateral gaps and a dual seat weighting inconsistent with the untouched holdout's worst seat.

P4G changes the estimator rather than tuning P4F.

One immutable chance corpus is generated once per flop and reused for every optimization round. On each policy iterate, every seat's pure empirical best response is learned on that corpus and its exploitability gap/gradient is evaluated on the **same corpus**. For the finite empirical game, the learned unilateral BR must be at least as good as the current behavioral policy (apart from numerical roundoff), eliminating the cross-block negative-gap pathology.

The final P4 acceptance sample remains completely independent. The fixed corpus is only an optimization/training set.

## Mathematical target

For each seat i and fixed empirical chance corpus C:

`E_i^C(sigma) = u_i^C(BR_i^C(sigma_-i), sigma_-i) - u_i^C(sigma)`.

P4G minimizes a smooth approximation to the worst-seat empirical exploitability:

`L_beta(sigma) = (1/beta) log sum_i exp(beta * E_i^C(sigma))`.

The corresponding seat weights are the softmax of the current empirical gaps. P4G uses predictor/corrector projected mirror-prox on the exact behavioral policy coordinates.

No strategic card abstraction is introduced. Exact global suit isomorphism remains the only card-state reduction.

## Frozen N=3 viability protocol

Exactly two cases:

1. rainbow `Ah 7d 2c`;
2. monotone `Ah 7h 2h`.

For both:

- provisional rake: 2%, uncapped for calibration;
- exact CFR warm start: `250k x 3` seeds;
- fixed FP warm start: `32 x 50k`, prior weight 4;
- fixed PED warm start: `32` rounds, `50k BR + 50k gradient`, initial coordinate step 0.10;
- P4G optimization corpus: exactly **50,000 chance deals**;
- corpus seed: **9802026**;
- the corpus is generated once and reused unchanged in every P4G round;
- corpus SHA256 is recorded in the audit artifact;
- P4G rounds: exactly **32**;
- smooth-worst-seat beta: **100.0**;
- predictor and corrector both recompute empirical BR + gap + gradient on the same immutable corpus;
- projected coordinate radius: `0.05 / sqrt(round)`;
- no early stopping;
- no texture-specific settings;
- no checkpoint selection;
- no parameter sweep after seeing results.

## Frozen acceptance gate

After all 32 rounds, run the original independent response validator:

- BR learning sample: 250,000;
- independent holdout sample: 250,000;
- validator seed: 9302026;
- intended exact-state coverage: 100%;
- PASS only if **every seat** has unilateral-gain 95% CI upper <= **0.030000 ante**.

The optimization corpus is not reused by this acceptance gate.

## Promotion rule

- If both N=3 cases PASS, freeze one N=4..8 scaling schedule before observing any N=4 result, then execute the existing rainbow/monotone representative texture gate exactly once for N=4..8.
- If either N=3 case FAILS, P4G is BLOCKED. Do not add more P4G rounds, enlarge the corpus, change beta/radius, select a favorable checkpoint or relax the response threshold. Change method.

This preserves the finite-roadmap discipline while directly testing whether common-random-number empirical optimization resolves the estimator instability exposed by P4F.
