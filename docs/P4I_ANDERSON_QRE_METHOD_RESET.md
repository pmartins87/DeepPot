# P4I — Anderson-accelerated QRE method reset

Date frozen: 2026-09-07

Status at freeze: **NO P4I viability result observed**

## Why P4I exists

P4H failed both frozen N=4 representative textures. Its audit showed that, at the final `tau=0.02` temperature, the last cyclic sweeps were still making large policy changes, including maximum coordinate moves close to 0.5. Therefore P4H was not close to a fixed point of its own logit-response operator.

P4I changes the numerical solver. It does **not** add more P4H sweeps or tune P4H parameters.

## Mathematical target

For each exact infoset `I`, define the current conditional action advantage

`A_I(sigma) = E[u(STAY)-u(FOLD) | I, sigma_-i]`.

At temperature `tau`, define the simultaneous logit-response operator

`G_tau(sigma)_I = logistic(A_I(sigma) / tau)`.

P4I seeks the fixed point

`sigma = G_tau(sigma)`

through deterministic Type-II Anderson acceleration on the residual

`F_tau(sigma) = G_tau(sigma) - sigma`.

The continuation path uses decreasing temperatures. Residuals are diagnostics only; they do not select a checkpoint and do not create an early-stopping gate.

## Core implementation change

Unlike P4H's reverse-seat Gauss-Seidel updates, P4I:

- estimates the response operator for **all seats simultaneously** on one immutable chance corpus;
- forms one global fixed-point residual vector;
- uses regularized Type-II Anderson acceleration with finite memory;
- blends the Anderson proposal with the ordinary Picard/logit target;
- projects each binary behavioral coordinate to `[0,1]`;
- executes a fixed number of iterations at every temperature.

Exact global suit isomorphism remains the only card-state reduction. No strategic card abstraction is introduced.

## Frozen N=4 viability protocol

Exactly two cases:

1. rainbow `Ah 7d 2c`;
2. monotone `Ah 7h 2h`.

Warm start for both is unchanged from P4H:

- provisional rake: 2%, uncapped for calibration;
- CFR: `250k x 3` seeds;
- FP: 32 rounds x 50k, prior weight 4;
- PED: 32 rounds, 50k BR + 50k gradient;
- P4G: 32 rounds on a fixed 50k corpus.

P4I itself is frozen as:

- P4I corpus: exactly **50,000** chance deals;
- corpus seed: **9912026**;
- temperatures: exactly `0.16 -> 0.08 -> 0.04 -> 0.02` ante;
- exactly **12 Anderson iterations per temperature**;
- Anderson memory: **5**;
- Type-II regularization ridge: **1e-8**;
- Anderson/Picard blend: **0.50 / 0.50**;
- projection: coordinate-wise `[0,1]`;
- no early stopping;
- no residual-based checkpoint selection;
- no parameter sweep after seeing results;
- no texture-specific parameters.

The 12-iteration count deliberately matches P4H's frozen 12 sweeps per temperature rather than extending the failed P4H iteration ladder. The solver is changed, not merely run longer.

## Frozen acceptance gate

After the final P4I iterate, run the original independent response validator unchanged:

- BR learning sample: 250,000;
- independent holdout sample: 250,000;
- validator seed: 9302026;
- intended policy coverage: 100%;
- PASS only if **every seat** unilateral-gain 95% CI upper <= **0.030000 ante**.

The P4I optimization corpus is not used by this acceptance gate.

## Promotion rule

- If both N=4 cases PASS, freeze one N=5..8 P4I scaling schedule before observing any P4I N=5 result, then execute it once.
- If either N=4 case FAILS, P4I is BLOCKED. Do not increase Anderson iterations/memory, alter ridge/blend/temperatures/corpus, select a favorable checkpoint, or relax the gate. Change method.
