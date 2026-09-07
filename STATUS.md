# DeepPot Status

Reference date: 2026-09-07

## Current state

**Base-first plan adopted.** The project follows the DeepKK philosophy in two stages:

`mathematical base strategy -> operational base runtime -> only then opponent exploitation`

The exploit/tracker work is intentionally deferred until the base solver and runtime are validated.

## Live mechanics now confirmed

- Pot Fold tables support up to **8 seats**.
- Dynamic player counts matter because tables are frequently not full.
- All dealt players pay equal ante; there are no practical SB/BB forced-blind payments.
- The **BTN is last to act** on the flop decision street.
- If every player before the last survivor folds, the survivor wins immediately without paying the fixed STAY contribution.
- Uncontested pots are still raked.

A true-HU observation with ante 12 each produced a BTN net profit of +11.52 after the other player folded. Interpreted as stack profit after the BTN's own ante, this exactly matches a 2% deduction from the 24 gross pot: 24 - 0.48 - 12 = 11.52.

Two other reported gross-to-award observations do not fit a single uncapped 2% rule:

- 84 -> 81.12: deduction 2.88 = 3.428571%
- 45 -> 43.38: deduction 1.62 = 3.600000%

Therefore the economy remains parameterized and the official rake schedule is **not frozen**.

## Engineering progress

### P1 game kernel — core complete

Implemented:

- 2–8 player Pot Fold state machine;
- neutral action order A0/A1/.../BTN, BTN last;
- fixed STAY cost = initial ante pot;
- automatic uncontested termination;
- zero-STAY BTN win when all previous players fold;
- showdown terminal state;
- nominal rake/cap model;
- per-player contributions, payouts, tie splitting and terminal utilities.

### P2 canonicalization/equity — prototype complete

Implemented:

- NLH card/deck model;
- flop canonicalization under all 24 suit permutations;
- flop+hole canonicalization under suit isomorphism;
- regression proving **1,755** canonical NLH flop classes;
- exact 5-card and 7-card evaluator;
- exact HU flop equity over all 990 turn-river runouts for two known hands;
- multiway showdown evaluation for known hole cards and final board.

### P3 base solver — first prototype implemented

Implemented a fixed-flop **chance-sampled CFR** engine:

- samples private cards plus turn/river once per iteration;
- traverses the complete binary FOLD/STAY tree for that sampled deal;
- uses information sets containing only public flop/history + actor's own hole cards;
- supports 2 through 8 players;
- supports CFR+ regret clipping and linear averaging;
- has deterministic seed behavior and smoke tests.

A reproducible pilot runner now exports source hash, run manifest, per-seed policies, visit coverage, pairwise policy differences and consensus stability metrics.

## First P4 stability pilot — FAILED, usefully

Pilot: HU, flop `Ah 7d 2c`, 2% working rake, 10,000 iterations per seed, seeds 1/2/3.

Coverage was nearly complete: 2,350 of 2,352 infosets were shared across all seeds (99.915%). But each exact infoset had only **8 median visits**.

Cross-seed results:

- mean absolute difference in P(STAY): about 0.214–0.217;
- P95 absolute difference: about 0.579–0.581;
- maximum difference: about 0.98;
- pairwise greedy-action agreement: only about 71–72%;
- all-seed greedy agreement: 57.62%;
- stability classification: **UNSTABLE**.

This is not a failure of the project. It is a gate doing its job: exact flop+hole infosets with shallow chance sampling are too sparse for a cheap all-flop run. We will not waste Ryzen time scaling this naive configuration to all 1,755 flops.

## Solver direction after the pilot

The next design step is **validated card abstraction + variance reduction**, not brute-force scaling.

Research reviewed on poker solvers supports suit-isomorphic card abstraction followed by equity/potential-aware bucketing. This is especially attractive in Pot Fold because turn and river contain chance only—there are no later strategic actions—so the future showdown-strength distribution is directly relevant to the only decision street.

DeepPot will evaluate a hierarchy rather than commit blindly to one bucket count:

1. exact suit-isomorphic state as truth/reference on small pilots;
2. per-flop equity/potential-aware buckets;
3. multiple bucket resolutions (coarse -> medium -> fine);
4. boundary refinement for buckets/states near action indifference;
5. reject any abstraction that materially changes best action or EV on validation samples.

## Validation already performed

- local combined suite before publication: 22 tests passed after adding stability auditing;
- GitHub CI on the current code path is passing;
- first 3-seed pilot is documented in `docs/PILOT_HU_A72R_10K_20260907.md`.

## Next critical work

1. Implement potential-aware/equity-distribution feature extraction for a fixed flop.
2. Implement deterministic clustering/bucketing without losing suit/blocker relationships silently.
3. Re-run the A72r HU pilot at several bucket resolutions and compare cross-seed stability.
4. Add an independent HU best-response/exploitability validator.
5. Only then choose the production abstraction and scale across the 1,755 canonical flops.

## Information still useful later, but not blocking development

For future observed hands, the most valuable record is:

`players dealt | ante | FOLD/STAY sequence | gross terminal pot | amount awarded | any separate fee/rake line | total award vs net stack change | rakeback/EXP credit`

No screenshots are required right now to continue base-solver development.
