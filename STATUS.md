# DeepPot Status

Reference date: 2026-09-07

## Current direction

DeepPot NLH Base v1 is now explicitly locked to the **same production methodology used for DeepKK**, adapted only for Pot Fold's larger postflop state space:

`enumerate all scenarios -> CFR+ -> linear average -> EV/CI confidence audit -> immutable mathematical TXT/CSV -> operational OpenHoldem -> runtime validation`

Authoritative decision: `docs/DEEPPOT_DEEPKK_METHOD_LOCK.md`.

P4C..P4I remain preserved as research diagnostics but are no longer release blockers and will not be extended into a P4J/P4K ladder.

## Current completed foundation

- mechanics: complete;
- economy: three live observations consistent with 2% gross-pot deduction; cap/profile variation still to freeze;
- exact game kernel: PASS;
- exact state representation: PASS;
- 1,755 canonical flops;
- 1,286,792 exact canonical `(flop, hero hole)` states;
- exact 2–8 player public action tree;
- CFR+ / linear-average solver implemented;
- resumable multiprocessing production runner implemented;
- measured throughput available for N=2..8;
- DeepKK-style EV/CI evaluator implemented;
- DeepKK-style mathematical TXT exporter implemented.

## Scenario catalogue

DeepPot enumerates every nonterminal public FOLD/STAY decision scenario, exactly following the DeepKK idea of explicit situations:

| N | scenarios |
|---:|---:|
| 2 | 2 |
| 3 | 6 |
| 4 | 14 |
| 5 | 30 |
| 6 | 62 |
| 7 | 126 |
| 8 | 254 |
| **total** | **494** |

`src/deeppot/deepkk_style_export.py` creates the canonical catalogue and one `STAY` list per scenario.

## Mathematical source format

Final `DeepPot.txt` will deliberately mirror DeepKK's organization:

- `##notes##` provenance;
- explicit modes/scenarios;
- exactly **494 named STAY lists**;
- absence from the current scenario's STAY list means FOLD;
- each list entry is an exact postflop state token `F####_H####` rather than a 169 preflop class;
- accompanying machine-readable CSV and SHA256 hashes.

Native OpenPPL handlists cannot encode a complete flop-relative exact state, so the immutable mathematical TXT keeps the list semantics while the operational layer compiles those lists to exact binary/DLL membership. This preserves the DeepKK mathematical-vs-operational separation rather than changing the strategic method.

## DeepKK-style confidence rule now implemented

`src/deeppot/deepkk_style_evaluator.py` evaluates every exact infoset with:

- EV(FOLD);
- EV(STAY);
- EV gap;
- standard error;
- CI95;
- effective visits / coverage;
- solver-average probability.

Final action rule follows DeepKK:

1. if `abs(EV_STAY - EV_FOLD) > CI95` and coverage is sufficient, use the EV-best action;
2. otherwise keep the solver-average greedy action;
3. never invent a replacement action for an inconclusive state.

This replaces the former universal `best-response <= 0.03 ante` release requirement.

## Current active phase

**P3 — unified DeepKK-style Ryzen generator/package: IN PROGRESS.**

Remaining work before handing the official training package to the Ryzen 9:

- combine solve + EV audit + final-strategy merge + `DeepPot.txt` export into one resumable command;
- choose and record one finite native DeepPot training/evaluation budget using the already-measured throughput;
- freeze economy/config/source hashes;
- package Windows/Ryzen instructions.

After that, the official Ryzen run produces the mathematical Base, then work proceeds directly to operational OpenHoldem integration and finite shadow/live runtime checks.

## Archived diagnostics

P4C through P4I remain in the repository only for reproducibility/research comparison. Any already-running workflow from that branch is non-decision-relevant to the production route.

## Useful remaining live economy evidence

For a clean Pot Fold payout observation capture:

`players dealt | ante | table/stake label | FOLD/STAY sequence | gross terminal pot | amount awarded | net stack change | separate fee/rake line | jackpot/other fee if present`

Highest-value remaining evidence is one reconstructable multiway hand and one relatively large pot to test whether a rake cap exists.
