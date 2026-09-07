# P4B HU A72r finite response gate — 2026-09-07

## Candidate

Exact-state 2M x 3-seed CFR+ consensus on `Ah 7d 2c`, provisional 2% rake.

- exact hole states: 1,176
- exact HU infosets: 2,352
- shared coverage: 100%
- pairwise greedy agreement: 94.69% to 95.24%

No strategic card abstraction is present.

## Predeclared response audit

The validator used two independent sample blocks:

- 250,000 samples to learn a deterministic unilateral response per exact information set;
- 250,000 independent holdout samples to estimate profile EV and unilateral response gain with paired 95% confidence intervals.

## Result before correction

- Player 0 BR gain: mean **0.016915 ante**, 95% upper bound **0.019005** — PASS against 0.02.
- Player 1 BR gain: mean **0.026804 ante**, 95% upper bound **0.028706** — FAIL against 0.02.
- Total response/NashConv-like gain: mean **0.043719 ante**, 95% upper bound **0.046533** — FAIL against 0.03.
- Unlearned P0 states: 0.
- Unreached P1 states in response learning: 0.

Therefore the original CFR consensus does **not** pass the finite HU release-quality gate. Increasing the A72r ladder to 5M/10M is explicitly prohibited by the roadmap.

## One allowed solver-method correction

The roadmap permits one targeted solver-method correction and one rerun of the failing gate.

The correction is a finite exact-state damped unilateral-response refinement starting from the 2M x 3 consensus:

- 12 fixed refinement rounds;
- 100,000 chance samples per round;
- no card abstraction;
- each round learns both players' pure unilateral responses against the current policy;
- current behavioral policy moves toward those responses with `alpha_t = 1 / (4 + t)`, from 0.20 down to 0.0625;
- then the exact same 250k learn + 250k holdout response gate is rerun once.

This correction is finite and predeclared. There is no parameter sweep and no second correction loop.
