# DeepPot Status

Reference date: 2026-09-07

## Current state

**Base-first + exact-state-first plan adopted.** The project follows the DeepKK philosophy in two stages:

`mathematical base strategy -> operational base runtime -> only then opponent exploitation`

The exploit/tracker work remains intentionally deferred until the base solver and runtime are validated.

The production research path now explicitly avoids strategically lossy card abstraction unless the exact route later fails a measured computational-feasibility gate.

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

### Exact state-space audit — completed

The initial shorthand `1,755 flops x 169 hands` is **not fully exact** because the 169 preflop classes merge suit relationships that become strategically different once a flop is visible.

Example: on `Qh 7h 2c`, `AhKh` and `AcKc` are both AKs, but only the first has the nut-heart flush draw.

The exact lossless count, quotienting only true global suit relabeling, was derived with Burnside's lemma and regression-tested:

- raw partitioned `(flop, hero hole)` states: **25,989,600**;
- canonical flops: **1,755**;
- exact suit-isomorphic flop+hole states: **1,286,792**;
- `1,755 x 169`: 296,595;
- exact state space is only **4.33855x** larger than the 169-class approximation;
- average exact hole states per canonical flop: **733.215**.

Exact public decision-scenario counts are `2^N - 2`:

- 2p: 2 scenarios -> 2,573,584 dense exact infosets over all flops;
- 3p: 6 -> 7,720,752;
- 4p: 14 -> 18,015,088;
- 5p: 30 -> 38,603,760;
- 6p: 62 -> 79,781,104;
- 7p: 126 -> 162,135,792;
- 8p: 254 -> 326,845,168.

These are dense global counts, not RAM requirements. Production solving can process one canonical flop at a time and export/checkpoint before moving to the next.

See `docs/EXACT_STATE_SPACE.md` and `src/deeppot/state_space.py`.

### P3 base solver — first prototype implemented

Implemented a fixed-flop **chance-sampled CFR** engine:

- samples private cards plus turn/river once per iteration;
- traverses the complete binary FOLD/STAY tree for that sampled deal;
- uses information sets containing only public flop/history + actor's own hole cards;
- supports 2 through 8 players;
- supports CFR+ regret clipping and linear averaging;
- has deterministic seed behavior and smoke tests.

A reproducible pilot runner exports source hash, run manifest, per-seed policies, visit coverage, pairwise policy differences and consensus stability metrics.

## First P4 stability pilot — unstable, but not evidence for abstraction

Pilot: HU, flop `Ah 7d 2c`, 2% working rake, 10,000 iterations per seed, seeds 1/2/3.

Coverage was nearly complete: 2,350 of 2,352 infosets were shared across all seeds (99.915%). But each exact infoset had only **8 median visits**.

Cross-seed results:

- mean absolute difference in P(STAY): about 0.214–0.217;
- P95 absolute difference: about 0.579–0.581;
- maximum difference: about 0.98;
- pairwise greedy-action agreement: only about 71–72%;
- all-seed greedy agreement: 57.62%;
- stability classification: **UNSTABLE**.

The correct interpretation is now: **10k sampled deals was a smoke test with far too few visits per exact infoset.** It does not demonstrate that the exact representation is computationally infeasible.

## Solver direction after exact-state audit

The next design step is **make exact solving fast enough before considering any strategically lossy abstraction**.

Priority order:

1. replace slow Python/string-key hot paths with dense integer-indexed structures where possible;
2. benchmark a much faster evaluator/terminal-payoff path;
3. batch/vectorize sampled deals and updates, borrowing from the DeepKK generator architecture;
4. add multiprocessing by canonical flop;
5. add checkpoint/resume and per-flop scheduling;
6. test variance-reduction / improved CFR sampling methods that keep exact infosets;
7. scale HU pilots through increasing visit targets and measure convergence vs wall time;
8. add independent HU best-response / response validation;
9. only after measured throughput, estimate total cost for 2p through 8p.

A lossy equity/potential abstraction is now a **fallback**, not the planned production representation.

## Precision terminology

DeepPot aims for:

- **100% state fidelity:** no strategically distinct flop/hole state is merged. This is achievable with the exact suit-isomorphic representation;
- numerical equilibrium/response accuracy pushed to explicit convergence tolerances. Finite iterative computation cannot literally provide infinite-precision equilibrium, so cross-seed stability, regret/response metrics and EV error bounds remain mandatory.

## Validation already performed

- existing combined unit suite was passing before the exact-state additions;
- exact Burnside state-count regressions were added;
- first 3-seed pilot is documented in `docs/PILOT_HU_A72R_10K_20260907.md`;
- exact-state design is documented in `docs/EXACT_STATE_SPACE.md`.

## Next critical work

1. Verify CI after the exact-state-count additions.
2. Build an exact-state throughput benchmark for representative flop textures.
3. Measure visits/second and memory/state for HU at 10k/50k/100k+ iterations.
4. Replace the main identified hot paths before using Ryzen time at scale.
5. Re-run cross-seed stability with materially higher visits per infoset.
6. Add HU best-response/response validation before expanding to 3w+.

## Information still useful later, but not blocking development

For future observed hands, the most valuable record is:

`players dealt | ante | FOLD/STAY sequence | gross terminal pot | amount awarded | any separate fee/rake line | total award vs net stack change | rakeback/EXP credit`

No screenshots are required right now to continue base-solver development.
