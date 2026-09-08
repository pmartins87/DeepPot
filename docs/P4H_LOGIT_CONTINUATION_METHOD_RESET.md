# P4H — deterministic cyclic logit-response continuation

Date frozen: 2026-09-07

Status at freeze: **NO P4H viability result observed**

## Why P4H exists

P4G fixed the estimator-sign pathology seen in P4F and passed N=3, but failed both N=4 textures and both completed N=5 textures under the untouched independent response gate. The N4 rainbow miss was large, so P4H changes the equilibrium-search method rather than tuning P4G.

P4H does not optimize aggregate exploitability gradients. It instead attacks the local behavioral Nash fixed-point equations directly through a deterministic logit-response homotopy.

Pot Fold has a simplifying property that is central here: each player acts at most once in a hand. Therefore each player's behavioral policy at an exact infoset is a single binary probability, and conditional STAY-vs-FOLD advantage is sufficient to define that player's local response operator.

## Mathematical operator

For exact infoset I controlled by seat i:

`A_i(I; sigma_-i) = E[u_i(STAY) - u_i(FOLD) | I, sigma_-i]`.

At temperature tau, P4H targets the logit response

`P_i(STAY | I) = sigmoid(A_i(I; sigma_-i) / tau)`.

As tau decreases, this smoothly approaches pure best response away from indifference. For a binary logit response exactly at a fixed point, the one-infoset entropy regularization scale is bounded by `tau * ln(2)`; at the frozen final tau 0.02 this quantity is about 0.01386 ante. This is motivation only, not an acceptance substitute. The independent unilateral-response gate remains decisive.

## Core algorithm

- one immutable chance corpus is built for P4H and reused for every update;
- seats are updated **cyclically in reverse action order**, BTN to first actor;
- after each seat update, the next seat sees the newly updated policy (Gauss-Seidel rather than simultaneous/Jacobi dynamics);
- each seat moves a fixed fraction toward its current empirical logit response;
- temperatures follow a frozen decreasing continuation path;
- no strategic card abstraction is introduced;
- final acceptance uses a separate split-sample response gate, not the training corpus.

This differs materially from P4C/P4D/P4E/P4F/P4G: it is a seat-wise fixed-point continuation method, not simultaneous BR averaging, exploitability descent, Nash-gradient extragradient, or worst-seat gradient minimization.

## Frozen N=4 viability protocol

Exactly two cases:

1. N=4 rainbow `Ah 7d 2c`;
2. N=4 monotone `Ah 7h 2h`.

For both cases:

- provisional economy: 2% rake, uncapped for calibration;
- exact CFR warm start: 250,000 iterations x 3 seeds;
- FP warm start: 32 x 50,000, prior weight 4;
- PED warm start: 32 rounds, 50,000 BR + 50,000 gradient samples/round;
- P4G warm start: 32 deterministic fixed-corpus rounds with 50,000 deals, beta 100, radius `0.05/sqrt(round)`, corpus seed 9802026;
- P4H independent optimization corpus: exactly **50,000 chance deals**;
- P4H corpus seed: **9902026**;
- P4H temperatures, in this exact order: **0.16, 0.08, 0.04, 0.02** ante;
- exactly **12 complete reverse-seat sweeps per temperature**;
- seat order in every sweep: seat 3, 2, 1, 0;
- update damping: **0.50** toward the current logit response;
- unreachable-on-corpus infosets are left unchanged in that seat update;
- no early stopping;
- no checkpoint selection;
- no texture-specific parameters;
- no temperature/damping/sample sweep after results.

Total P4H seat updates per N=4 case: `4 temperatures x 12 sweeps x 4 seats = 192`.

## Frozen acceptance gate

After the final tau=0.02 sweep:

- BR-learning sample: 250,000;
- independent holdout sample: 250,000;
- validator seed: 9302026;
- intended exact-state coverage: 100%;
- PASS only if every seat unilateral-gain 95% CI upper <= **0.030000 ante**.

## Promotion rule

- If both N=4 cases PASS, freeze one P4H N=5..8 scaling schedule before observing any N=5 P4H result and execute the eight predefined rainbow/monotone cases once.
- If either N=4 case FAILS, mark P4H BLOCKED. Do not add sweeps, temperatures, larger corpus, altered damping, favorable checkpoint selection, or relaxed threshold. Change method.

P4G remains a valid frozen N=3 method because it passed both N=3 gates. P4H is currently being evaluated only as the candidate production method for N>=4.
