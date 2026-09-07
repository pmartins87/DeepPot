# DeepPot Status

Reference date: 2026-09-07

## Current state

DeepPot NLH Base v1 remains on the **base-first / exact-state-first** path:

`mathematical base strategy -> operational OpenHoldem runtime -> only then DeepKK-style exploitation`

No strategically lossy card abstraction is planned for Base v1. Exact global suit isomorphism is the only card-state reduction.

Current phase summary:

- **P0 mechanics:** complete;
- **P0 economy:** pending final freeze;
- **P1 game kernel:** PASS;
- **P2 exact state/equity representation:** PASS;
- **P3 exact solver engine + throughput gate:** PASS;
- **P4 HU:** PASS and closed;
- **P4C original multiway CFR/FP:** BLOCKED;
- **P4D FP-PED:** BLOCKED;
- **P4E projected Nash extragradient:** N=3 finite viability gate RUNNING;
- P5+ waits for P0/P4 closure.

## Mechanics confirmed

- Pot Fold supports 2 through 8 dealt players in the DeepPot model/live observations;
- every dealt player pays the same ante;
- preflop is skipped;
- action is one flop decision street;
- legal strategic actions are FOLD or fixed POT/STAY;
- BTN acts last;
- when all earlier players fold, the last survivor wins without paying STAY;
- after flop action leaves 2+ players, turn and river are automatic;
- uncontested pots are also subject to deduction/rake.

## P0 economy

The official KKPoker Pot Fold rules page does not publish a Pot-Fold-specific rake schedule. DeepPot therefore keeps economy separate from strategy mechanics and does not silently inherit the normal NLH table.

Three user-reported payout observations are currently consistent with a **2% deduction from gross terminal pot** once the displayed winner amount is interpreted as net profit rather than gross pot award. The true-HU ante-12 uncontested observation is directly consistent with 2%:

`gross 24 -> deduction 0.48 -> winner net profit 11.52 after own ante 12`.

The remaining uncertainty is primarily whether Pot Fold has a cap or stake/profile-dependent variation. Until frozen, calibration uses the explicit provisional profile `provisional-2pct` and P5 all-flop production solving does not start.

Finite evidence ledger: `docs/P0_ECONOMY_EVIDENCE.md`.

## P1 — game kernel: PASS

Implemented and regression-tested:

- exact 2–8 player binary public tree;
- fixed STAY cost = initial ante pot;
- uncontested/showdown terminals;
- contributions, payouts, ties and utilities;
- parameterized rake/cap.

## P2 — exact state/equity representation: PASS

Frozen lossless state model:

- 1,755 canonical NLH flops under global suit isomorphism;
- **1,286,792** exact `(canonical flop, hero hole)` states;
- exact per-flop dense hole-state indices;
- public decision scenarios `2^N - 2`;
- exact dense infoset keys;
- direct exact 7-card evaluator with differential regression;
- exact HU runout equity API;
- multiway showdown evaluator.

The old `1,755 x 169` shorthand is not production-safe because visible-flop suit relationships make nominally identical preflop classes strategically different.

## P3 — exact solver/throughput: PASS

The exact fixed-flop chance-sampled CFR+ engine, consensus export, checkpoint/resume, all-flop queue, hashing/manifests and multiprocessing path are implemented.

Frozen post-optimization throughput on `Ah 7d 2c`:

| N | fixed iterations | iterations/s | infoset-visits/s |
|---:|---:|---:|---:|
| 2 | 50,000 | 11,806 | 23,612 |
| 3 | 20,000 | 5,557 | 33,342 |
| 4 | 10,000 | 2,659 | 37,224 |
| 5 | 5,000 | 1,314 | 39,429 |
| 6 | 2,000 | 638 | 39,536 |
| 7 | 1,000 | 309 | 38,940 |
| 8 | 500 | 146.6 | 37,243 |

No further throughput ladder is planned.

## P4 — finite strategy-quality calibration

### HU: PASS / CLOSED

All four frozen HU representative textures pass the independent split-sample unilateral-response gate after the single allowed 12-round damped bilateral response refinement.

Provisional-economy HU production method:

`2M x 3 CFR consensus -> 12 x 100k damped-response refinement`.

### P4C original multiway CFR/FP: BLOCKED

All 12 raw N=3..8 representative cases failed the unchanged per-seat unilateral-gain upper threshold of 0.03 ante. The one allowed 32-round fictitious-response correction was applied to N=3..6 and all eight corrected cases still failed. No more P4C tuning is allowed.

### P4D FP-PED: BLOCKED

Frozen N=3 viability results:

| flop | seat 0 upper | seat 1 upper | seat 2 upper | result |
|---|---:|---:|---:|---|
| `Ah 7h 2h` | 0.005327 | 0.011187 | 0.015921 | PASS |
| `Ah 7d 2c` | 0.020422 | 0.018494 | **0.039123** | FAIL |

The rainbow failure blocks P4D. No extra rounds, samples, altered radius or checkpoint selection are allowed.

### P4E projected Nash extragradient: RUNNING

P4E changes the mathematical target. For each exact infoset it estimates the player's own conditional action advantage:

`A(I) = E[u(STAY) - u(FOLD) | I, opponents]`

and applies an independent predictor/corrector projected extragradient to the binary Nash complementarity conditions.

Frozen N=3 viability protocol:

- rainbow `Ah 7d 2c` and monotone `Ah 7h 2h` only;
- CFR warm start `250k x 3`;
- 64 extragradient rounds;
- 50k predictor + 50k independent corrector samples/round;
- radius `0.10 / sqrt(round)`;
- original 250k-learn + 250k-holdout response validator;
- every seat upper 95% <= 0.03 ante;
- no early stopping/tuning/checkpoint selection.

The N=4..8 promotion schedule was predeclared **before the N=3 results were known** in `docs/P4E_N4_N8_SCALING_SCHEDULE.md`. Its workflow is prepared but deliberately gated by `.github/p4e_n4_n8.trigger`, so it cannot run unless both N=3 cases pass first.

Current N=3 workflow run: `34160799208`.

## Next branch

If both P4E N=3 cases PASS, create the predeclared trigger and execute the ten N=4..8 rainbow/monotone promotion cases exactly once. If either fails, mark P4E BLOCKED and change solver method rather than adding a parameter ladder.

P5 all-1,755-flop production solving begins only after both P0 economy and P4 calibration are closed.

## Information useful from live Pot Fold

For any clean payout observation, capture:

`players dealt | ante | table/stake label | FOLD/STAY sequence | gross terminal pot | amount awarded | net stack change | separate fee/rake line | jackpot/other fee if present`

The remaining P0 goal is to establish whether the apparent 2% gross-pot deduction has a cap or profile variation.
