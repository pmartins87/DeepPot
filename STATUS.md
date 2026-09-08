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
- **P4E projected Nash extragradient:** BLOCKED;
- **P4F primal-dual worst-seat mirror-prox:** BLOCKED;
- **P4G deterministic fixed-corpus worst-seat mirror-prox:** N=3 PASS; N>=4 BLOCKED by scaling gate;
- **P4H deterministic cyclic logit-response continuation:** N=4 viability gate RUNNING;
- P5+ waits for P0/P4 closure.

## Mechanics/economy

Confirmed mechanics: 2–8 dealt players, equal ante, no preflop betting, one flop FOLD or POT/STAY decision, BTN last, automatic turn/river if 2+ remain, uncontested last-survivor terminal, and uncontested pots are raked.

The official KKPoker Pot Fold rules page still does not publish a Pot-Fold-specific rake schedule. Three user-reported payouts are mutually consistent with a **2% deduction from gross terminal pot**. The remaining P0 uncertainty is primarily cap/profile variation. Engineering continues under explicit provisional profile `provisional-2pct`; P5 waits for the final economy freeze. Evidence ledger: `docs/P0_ECONOMY_EVIDENCE.md`.

## P1/P2/P3

P1 game kernel, P2 exact representation/evaluator, and P3 solver/throughput infrastructure are PASS. Frozen exact representation is 1,755 canonical flops and **1,286,792** exact `(canonical flop, hero hole)` states under global suit isomorphism only. Production checkpoint/resume, per-flop queue, hashing/manifests and multiprocessing are implemented.

Frozen P3 throughput on `Ah 7d 2c` after the single optimization pass:

| N | iterations/s | infoset-visits/s |
|---:|---:|---:|
| 2 | 11,806 | 23,612 |
| 3 | 5,557 | 33,342 |
| 4 | 2,659 | 37,224 |
| 5 | 1,314 | 39,429 |
| 6 | 638 | 39,536 |
| 7 | 309 | 38,940 |
| 8 | 146.6 | 37,243 |

No further throughput ladder is planned.

## P4 HU — PASS / CLOSED

All four frozen HU representative textures pass the independent split-sample unilateral-response gate after the single allowed 12-round damped bilateral response refinement.

Provisional-economy HU production method:

`2M x 3 CFR consensus -> fixed 12 x 100k damped-response refinement`.

## P4 multiway history

P4C, P4D, P4E and P4F are blocked under their frozen protocols. Thresholds were not relaxed and no extra iteration/parameter ladders were added.

### P4G — N=3 PASS / N>=4 BLOCKED

P4G fixed the negative same-corpus gap pathology and passed both N=3 representative cases:

| flop | seat 0 upper | seat 1 upper | seat 2 upper | result |
|---|---:|---:|---:|---|
| `Ah 7h 2h` | 0.007285 | 0.009602 | 0.011770 | PASS |
| `Ah 7d 2c` | 0.021620 | 0.022696 | 0.029529 | PASS |

However the predeclared N=4..8 scaling workflow failed both completed N=4 textures and both completed N=5 textures despite 100% coverage and zero material negative-gap stages:

| case | unilateral-gain 95% CI uppers | result |
|---|---|---|
| N4 rainbow | 0.075952, 0.058691, 0.049807, 0.053125 | FAIL |
| N4 monotone | 0.036477, 0.035742, 0.025135, 0.023640 | FAIL |
| N5 rainbow | 0.190325, 0.146310, 0.094401, 0.085317, 0.054973 | FAIL |
| N5 monotone | 0.104327, 0.076474, 0.066987, 0.035960, 0.030935 | FAIL |

Threshold remains every seat <= **0.030000 ante**. Therefore P4G is **BLOCKED for N>=4**. The already-running N6..8 matrix jobs are no longer decision-relevant and cannot reopen P4G. Full record: `docs/P4G_SCALING_RESULT.md`.

### P4H — RUNNING

P4H changes the method rather than tuning P4G. It solves the local behavioral fixed-point equations through deterministic cyclic logit-response continuation:

- immutable P4H chance corpus;
- seat-wise Gauss-Seidel updates in reverse action order (BTN to first actor);
- binary logit response based on exact-infoset conditional `STAY-FOLD` advantage;
- frozen temperatures `0.16 -> 0.08 -> 0.04 -> 0.02` ante;
- exactly 12 reverse-seat sweeps per temperature;
- damping 0.50;
- no early stopping/checkpoint selection/parameter sweep;
- independent original response gate remains decisive.

The method, tests and N=4 protocol were frozen before any P4H result in `docs/P4H_LOGIT_CONTINUATION_METHOD_RESET.md`. CI passed before trigger.

Current P4H N=4 workflow run: `34173556322`.

## Next branch

If both frozen P4H N=4 cases PASS, freeze one N=5..8 P4H scaling schedule before observing any P4H N=5 result and execute it once. If either N=4 case fails, mark P4H BLOCKED and change method; do not tune P4H.

P5 all-1,755-flop production solving begins only after both P0 economy and P4 calibration are closed.

## Information useful from live Pot Fold

For any clean payout observation, capture:

`players dealt | ante | table/stake label | FOLD/STAY sequence | gross terminal pot | amount awarded | net stack change | separate fee/rake line | jackpot/other fee if present`

The remaining P0 goal is to establish whether the apparent 2% gross-pot deduction has a cap or profile variation.
