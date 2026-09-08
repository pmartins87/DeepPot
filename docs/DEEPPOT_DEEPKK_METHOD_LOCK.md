# DeepPot — DeepKK-method lock

Date: 2026-09-07

## Decision

DeepPot NLH Base will use the same engineering/mathematical pattern used to create DeepKK, adapted only where Pot Fold postflop necessarily has a larger state space.

This document supersedes the idea that P4C/P4D/P4E/P4F/P4G/P4H/P4I-style exploitability gates are release blockers for Base v1. Those experiments are preserved as research history and diagnostics, but they do not define the production method.

## Canonical pattern inherited from DeepKK

1. Enumerate every decision scenario for each supported player count.
2. Train one immutable mathematical base strategy with CFR+ and linear averaging.
3. Separately evaluate FOLD versus the aggressive action at each information set.
4. Record EV gap, standard error, 95% confidence interval and coverage/visits.
5. If the EV comparison is statistically confident, use its best action.
6. If it is not statistically confident, keep the solver-average greedy action rather than inventing a new action.
7. Export an immutable mathematical source strategy plus machine-readable CSV/metadata/hashes.
8. Build a separate operational OpenHoldem representation from the immutable mathematical source.
9. Tracking/exploitation is a later layer; ambiguity always falls back to the mathematical base.

This is deliberately the DeepKK pattern, not a new solver-research programme.

## What changes only because Pot Fold is postflop

DeepKK could represent a decision with `scenario x 169 preflop handclass`. DeepPot cannot safely collapse a visible flop to the same 169-class representation because suit/rank relationships to the board matter strategically.

Therefore the DeepKK concept `handclass` is replaced by the exact lossless state key:

`canonical_flop_id + exact_flop_relative_hole_state_id`.

This is not a new strategic method. It is only the minimum state representation required to apply the same DeepKK method after the flop.

## Scenario catalogue

For N dealt players, every nonterminal fixed-order FOLD/STAY public history is a scenario, exactly as DeepKK enumerated its AoF situations.

Counts:

- N=2: 2 scenarios
- N=3: 6 scenarios
- N=4: 14 scenarios
- N=5: 30 scenarios
- N=6: 62 scenarios
- N=7: 126 scenarios
- N=8: 254 scenarios

Total: **494 strategic scenarios**.

The BTN all-prior-FOLD history is terminal and therefore has no decision, analogous to DeepKK's technical no-decision/walk situations.

## DeepPot.txt mathematical source

The final mathematical `DeepPot.txt` must intentionally resemble `DeepKK.txt`:

- `##notes##` with economy/version/hash provenance;
- explicit game-mode/scenario catalogue;
- one named STAY list for every strategic scenario;
- FOLD as the default action outside the scenario's STAY list;
- no opponent-exploitation logic in the mathematical base.

There will be **494 scenario lists**.

Because OpenPPL native handlists encode preflop 169-style hole-card classes and cannot themselves encode a complete exact flop-relative state, the mathematical TXT list entries use stable exact-state tokens such as `F0123_H0456`. The operational OpenHoldem layer compiles those exact lists to a binary/DLL lookup while preserving the same scenario/list semantics. This mirrors the DeepKK separation between mathematical source and operational formula rather than changing the strategy.

## Training budget

We copy the DeepKK method, not blindly the numerical meaning of one inner loop. DeepKK's `deals_per_iter` was a vectorized preflop engine operation; one DeepPot solver iteration already samples a full postflop chance deal and traverses the full binary public tree for a fixed flop. Therefore raw loop counts are not semantically interchangeable.

The official DeepPot run must nevertheless expose the same classes of controls used by DeepKK:

- CFR+ on;
- linear average on;
- deterministic seed recorded;
- finite training budget;
- separate EV-audit sample budget;
- minimum visits/effective visits;
- confidence rule `abs(EV_STAY - EV_FOLD) > CI95`;
- solver-average fallback for inconclusive states;
- resumable execution;
- final manifest and SHA256 hashes.

The first official Ryzen package will choose one finite budget based on already-measured DeepPot throughput and then run production, rather than introducing another algorithm ladder.

## P4C..P4I status

Preserve all code/results for reproducibility, but classify them as **research diagnostics, non-blocking for the DeepKK-parity production route**. No P4J/P4K chain is created.

## Definition of success for the base

DeepPot Base v1 is complete when:

1. the official Ryzen run covers the planned N=2..8 production state space under the frozen economy;
2. the DeepKK-style EV/CI/coverage audit is exported;
3. `DeepPot.txt` and machine-readable strategy files are generated and hashed;
4. the operational OpenHoldem layer identifies the same scenario/exact state and returns FOLD or POT/STAY;
5. shadow/live runtime checks show correct state recognition and legal actions.

Opponent modelling/exploitation comes only after that base is operational.
