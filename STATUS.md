# DeepPot Status

Reference date: 2026-09-07

## Current state

**Base-first plan adopted.** The project will reproduce the DeepKK philosophy in two stages:

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

This is deliberately marked **prototype**, not final solver. Path-dependent rake makes utilities non-constant-sum, and N>2 is multiplayer. Those facts require explicit validation before we treat CFR convergence as a production equilibrium guarantee.

## Validation already performed locally before publication

The new card/canonicalization/evaluator/economy/solver test suite was executed together with the existing kernel tests: **20 tests passed** in the local validation mirror before the GitHub files were published.

GitHub Actions remains the repository CI gate for the committed tree.

## Next critical work

1. Add production run configuration/manifest analogous to DeepKK.
2. Build cross-seed/stability metrics for a small HU canonical-flop pilot.
3. Implement a HU best-response/exploitability validator independent of the training update rule.
4. Add multiprocessing/checkpointing by canonical flop.
5. Benchmark exact-state storage and determine whether abstraction is needed.
6. Only after the base solver passes P4, scale from HU pilots to all 1,755 flops and then N=3..8.

## Information still useful later, but not blocking development

For future observed hands, the most valuable record is:

`players dealt | ante | FOLD/STAY sequence | gross terminal pot | amount awarded | any separate fee/rake line | total award vs net stack change | rakeback/EXP credit`

No screenshots are required right now to continue base-solver development.
