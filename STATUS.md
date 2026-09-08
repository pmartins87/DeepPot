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
- **P4G deterministic fixed-corpus worst-seat mirror-prox:** N=3 PASS; N>=4 BLOCKED;
- **P4H cyclic logit continuation:** BLOCKED at N=4;
- **P4I Anderson-accelerated QRE continuation:** N=4 finite viability gate RUNNING;
- **P5+** waits for P0/P4 closure.

## Mechanics/economy

Confirmed mechanics: 2–8 dealt players, equal ante, no preflop betting, one flop FOLD or POT/STAY decision, BTN last, automatic turn/river when 2+ remain, uncontested last-survivor terminal, and uncontested pots are raked.

Three user-reported payouts remain mutually consistent with **2% of gross terminal pot**. The unresolved P0 question is principally cap/profile variation. Engineering continues under explicit provisional profile `provisional-2pct`; final P5 production solving waits for P0 PASS. Evidence ledger: `docs/P0_ECONOMY_EVIDENCE.md`.

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

All four frozen HU representative textures pass the independent split-sample unilateral-response gate after the one allowed 12-round damped bilateral response refinement.

Provisional-economy HU production method:

`2M x 3 CFR consensus -> fixed 12 x 100k damped-response refinement`.

## P4 multiway history

P4C, P4D, P4E and P4F are blocked under their frozen protocols. Thresholds were not relaxed and no parameter/iteration ladders were added.

### P4G — N=3 PASS / N>=4 BLOCKED

P4G passed both N=3 representative textures, including rainbow seat 2 at `0.029529`. Its frozen N=4 scaling then failed both textures, and N=5 also failed both. Thus P4G cannot be promoted beyond N=3. Full record: `docs/P4G_SCALING_RESULT.md`.

### P4H — BLOCKED

Frozen N=4 run `34173556322` failed both textures with 100% policy coverage:

| flop | seat 0 upper | seat 1 upper | seat 2 upper | seat 3 upper | result |
|---|---:|---:|---:|---:|---|
| `Ah 7d 2c` | 0.050204 | 0.070360 | 0.139722 | 0.167616 | FAIL |
| `Ah 7h 2h` | 0.015154 | 0.017002 | 0.041315 | 0.076306 | FAIL |

The final `tau=0.02` cyclic sweeps were still moving some coordinates by roughly 0.5, so P4H had not numerically reached its own logit fixed point. This is recorded in `docs/P4H_RESULT.md`. Per the frozen rule, P4H receives no more sweeps/damping/temperature/corpus tuning.

### P4I — RUNNING

P4I changes the numerical fixed-point solver instead of extending P4H. It forms the simultaneous exact-infoset logit-response map for all seats on one immutable corpus and applies regularized Type-II Anderson acceleration to the global residual.

Frozen N=4 protocol is in `docs/P4I_ANDERSON_QRE_METHOD_RESET.md`:

- same N=4 CFR -> FP -> PED -> P4G warm start;
- immutable 50,000-deal P4I corpus, seed `9912026`;
- temperatures `0.16 -> 0.08 -> 0.04 -> 0.02`;
- exactly 12 Anderson iterations per temperature;
- memory 5, ridge `1e-8`, Anderson/Picard blend 0.50;
- residual is diagnostic only; no early stop/checkpoint selection;
- unchanged independent 250k-learn + 250k-holdout response gate;
- PASS only if every seat 95% unilateral-gain upper <= `0.030000 ante`.

The all-seat operator was regression-tested against independent P4H per-seat operator passes; deterministic replay and simplex preservation tests also pass CI.

Current P4I N=4 workflow run: `34177615764`.

## Next branch

If both frozen P4I N=4 cases PASS, freeze one N=5..8 P4I scaling schedule before seeing any P4I N=5 result and execute it once. If either N=4 case fails, mark P4I BLOCKED and change method; do not tune P4I.

P5 all-1,755-flop production solving begins only after P0 economy and P4 calibration are both closed.

## Information useful from live Pot Fold

For a clean payout observation capture:

`players dealt | ante | table/stake label | FOLD/STAY sequence | gross terminal pot | amount awarded | net stack change | separate fee/rake line | jackpot/other fee if present`

The remaining P0 goal is to establish whether the apparent 2% gross-pot deduction has a cap or profile variation.
