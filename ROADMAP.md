# DeepPot NLH Base v1 — finite execution roadmap

## Definition of done

This roadmap ends when **DeepPot NLH Base v1 is playing Pot Fold on the user's computer through OpenHoldem**, using the mathematical base strategy only.

Base v1 must:

- support 2 through 8 dealt players;
- preserve every strategically distinct flop+hole state, collapsing only true global suit isomorphisms;
- choose only FOLD or POT/STAY according to the solved policy;
- use the frozen Pot Fold economy for the table/stake configuration being played;
- log detected state, policy lookup and final action;
- fail closed on unknown or inconsistent runtime state;
- pass the finite shadow/live gates below.

Opponent exploitation, tracker statistics and PLO are **not blockers for Base v1**. They are later projects after the base IA is operational.

## Execution discipline — no infinite test ladders

1. The phases and gates below are the complete path to Base v1.
2. We do **not** add another iteration rung merely because a probability-stability number can be improved further.
3. A failed gate receives at most **one planned solver/implementation correction and one rerun of the failing gate**. If it still fails, the phase is explicitly BLOCKED and we change the method; we do not keep adding tests.
4. New unit/regression tests are allowed only when needed to protect a concrete bug fix or a roadmap feature. They do not create new validation phases.
5. Cross-seed probability agreement is diagnostic. Release quality is decided primarily by state coverage, EV/response quality and runtime correctness.
6. Strategic card abstraction is not planned for Base v1. It may be reconsidered only if the exact path reaches a documented compute blocker after the single optimization pass allowed by this roadmap.

---

# P0 — Mechanics and economy freeze

Status: **MECHANICS COMPLETE / ECONOMY PENDING**

Completed:

- [x] no practical SB/BB forced-blind payments; every dealt player posts the same ante;
- [x] preflop skipped;
- [x] one flop decision street;
- [x] FOLD or fixed POT/STAY action;
- [x] BTN last to act;
- [x] 2–8 dealt players;
- [x] automatic turn/river after the flop action when 2+ players remain;
- [x] uncontested terminal when everybody before the last survivor folds;
- [x] uncontested pots are raked.

Economy closure:

- [ ] freeze Pot Fold rake percentage/cap/rules for the stake configuration used by Base v1;
- [ ] freeze whether any separately attributed reward/rakeback component should enter decision EV;
- [ ] encode economy profile ID into every production policy manifest.

Finite evidence rule: use a Pot-Fold-specific official KKPoker schedule if one becomes available. Otherwise use **at most 12 clean live payout observations** chosen across relevant player-count/pot geometries. If those prove that more than one economy profile exists, Base v1 supports only the profile(s) actually identified; we do not keep collecting an unlimited sample.

The three live payouts currently reported are mutually consistent with **2% of gross terminal pot** once 84/45 are interpreted consistently as pre-rake net wins rather than gross pots; see `docs/P0_ECONOMY_EVIDENCE.md`. Cap behavior is still unknown.

Engineering may continue under the current provisional 2% model. **Final all-flop production solving waits for P0 PASS.**

---

# P1 — NLH game kernel

Status: **PASS**

- [x] card/deck model;
- [x] exact 2–8 player Pot Fold action tree;
- [x] fixed continue cost = initial ante pot;
- [x] BTN-last neutral action order;
- [x] uncontested and showdown terminals;
- [x] parameterized rake/cap;
- [x] tie splitting and per-player utilities;
- [x] core regression tests.

No further work is planned in P1 unless a concrete live-mechanics bug is discovered.

---

# P2 — Lossless card/state representation

Status: **PASS**

- [x] 1,755 canonical NLH flops under suit isomorphism;
- [x] exact flop+hole canonicalization;
- [x] exact state-space proof/regression: **1,286,792** flop+hole states modulo only true suit relabeling;
- [x] exact per-flop dense hole-state index;
- [x] dense public-history IDs for 2–8 players;
- [x] dense exact infoset keys;
- [x] exact 5/7-card evaluator;
- [x] faster direct exact 7-card evaluator;
- [x] differential regression against the original exact evaluator;
- [x] exact HU 990-runout equity API;
- [x] multiway showdown evaluator.

The old shorthand `1,755 x 169` is not used in production because it merges strategically different post-flop suit relationships.

---

# P3 — Exact solver engine and throughput gate

Status: **PASS**

Implemented and frozen for the Base-v1 path:

- [x] fixed-flop exact-state chance-sampled CFR+ candidate;
- [x] linear average strategy;
- [x] full binary action-tree traversal per sampled deal;
- [x] dense integer infoset keys;
- [x] precomputed raw-hole -> exact-state map;
- [x] direct exact terminal evaluator;
- [x] evaluate each player's final rank once per sampled deal and reuse it across terminal branches;
- [x] reproducible manifests and seed policies;
- [x] cross-seed exact consensus-policy export;
- [x] multiprocessing across independent seeds for pilots;
- [x] checkpoint/resume per canonical flop;
- [x] resumable all-flop work queue;
- [x] multiprocessing by canonical flop for the Ryzen 9;
- [x] per-shard policy SHA256 plus source/config/economy hashes;
- [x] production manifest with atomic progress updates;
- [x] exact-coverage enforcement before shard publication.

Compact node storage was **not required** by the fixed P3 gate and is therefore not a new prerequisite.

### Finite throughput gate — CLOSED

The one fixed N=2..8 benchmark and the **single allowed implementation-optimization rerun** were completed on `Ah 7d 2c`. Post-optimization throughput:

| N | fixed iterations | iterations/s | infoset-visits/s |
|---:|---:|---:|---:|
| 2 | 50,000 | 11,806 | 23,612 |
| 3 | 20,000 | 5,557 | 33,342 |
| 4 | 10,000 | 2,659 | 37,224 |
| 5 | 5,000 | 1,314 | 39,429 |
| 6 | 2,000 | 638 | 39,536 |
| 7 | 1,000 | 309 | 38,940 |
| 8 | 500 | 146.6 | 37,243 |

**No third throughput benchmark is allowed.**

---

# P4 — Finite solver-quality calibration

Status: **IN PROGRESS — HU PASS / P4C BLOCKED / P4D BLOCKED / P4E RUNNING**

## P4A — HU A72r ladder: CLOSED

Completed fixed ladder on `Ah 7d 2c`, provisional 2% rake:

- [x] 10k x 3 seeds;
- [x] 50k x 3 seeds;
- [x] 250k x 3 seeds;
- [x] 1M x 3 seeds;
- [x] 2M x 3 seeds.

At 2M x 3:

- 100% shared infoset coverage;
- ~1,700 median visits/infoset;
- pairwise greedy agreement ~94.7–95.2%;
- all-three greedy agreement 92.56%;
- pairwise mean absolute P(STAY) difference ~0.037–0.038.

**No 5M/10M/etc A72r seed ladder will be added.**

## P4B — HU response gate: PASS

Implemented a split-sample unilateral-best-response validator with an independent holdout and 95% CI. Frozen gate:

- coverage = 100%;
- pairwise greedy agreement >= 90%;
- player-0 unilateral gain 95% upper <= **0.02 ante**;
- player-1 unilateral gain 95% upper <= **0.02 ante**;
- total/NashConv gain 95% upper <= **0.03 ante**.

The raw 2M x 3 CFR consensus did not pass every response threshold. The roadmap's **single allowed solver-method correction** was therefore used: 12 fixed damped bilateral response-refinement rounds, 100k chance samples/round, prior weight 4, deterministic schedule, no card abstraction. The same 250k-learn + 250k-holdout gate was then rerun exactly once.

All four frozen representative HU textures PASS after that one correction:

| flop | texture | min pairwise greedy | P0 BR 95% upper | P1 BR 95% upper | total 95% upper |
|---|---|---:|---:|---:|---:|
| `Ah 7d 2c` | rainbow | >= 0.947 | 0.009384 | 0.016132 | 0.024312 |
| `Ah 7h 2c` | two-tone | 0.967406 | 0.008217 | 0.010676 | 0.017796 |
| `Ah 7h 2h` | monotone | 0.984012 | 0.007234 | 0.004585 | 0.011112 |
| `Ah Ad 2c` | paired | 0.944220 | 0.008125 | 0.012350 | 0.019316 |

**HU calibration is closed.** The provisional-economy HU production method is `2M x 3 CFR consensus -> fixed 12 x 100k damped-response refinement`.

## P4C — Original multiway CFR/FP path: BLOCKED

The frozen representative gate was executed on all 12 N/texture cases:

- N=3..8;
- `Ah 7d 2c` rainbow;
- `Ah 7h 2h` monotone.

Every raw CFR candidate had 100% intended exact-state coverage, but **all 12 failed** the unchanged per-seat unilateral-gain threshold of 0.03 ante.

The one permitted correction was then applied to the already-failed N=3..6 cases: 32 rounds of finite multiplayer fictitious-response averaging, with 50k samples/round for N=3/4 and 25k for N=5/6, followed by exactly one rerun of the original response gate.

All eight corrected N=3..6 cases still failed. Corrected worst-seat 95% upper bounds:

| N | rainbow | monotone | threshold |
|---:|---:|---:|---:|
| 3 | 0.070115 | 0.031408 | <= 0.030000 |
| 4 | 0.131516 | 0.061585 | <= 0.030000 |
| 5 | 0.238271 | 0.149504 | <= 0.030000 |
| 6 | 0.310460 | 0.204696 | <= 0.030000 |

Because the single correction failed, **P4C is BLOCKED**. We do not add CFR iterations, extra FP rounds, new alpha schedules or relaxed thresholds. We also do not spend compute applying the disproven P4C correction to N=7/8.

The exact multiway response validator has additionally passed a differential N=2 comparison against the independent HU validator, supporting the validity of the measured multiway response gaps.

## P4D — FP-PED method reset: BLOCKED

P4D replaced fictitious-response averaging as the final solver with exact-state sampled Projected Exploitability Descent (PED), using the fixed N=3 viability protocol recorded before results in `docs/P4D_FP_PED_METHOD_RESET.md`.

The two frozen N=3 results were:

| flop | seat 0 upper | seat 1 upper | seat 2 upper | gate |
|---|---:|---:|---:|---|
| `Ah 7h 2h` monotone | 0.005327 | 0.011187 | 0.015921 | PASS |
| `Ah 7d 2c` rainbow | 0.020422 | 0.018494 | **0.039123** | FAIL |

Coverage was 100% in both cases. Because the max-state rainbow case exceeded the unchanged 0.03 threshold, P4D is **BLOCKED**. We do not add PED rounds, alter the PED radius schedule, increase its samples, select an earlier checkpoint or relax the gate.

## P4E — projected Nash extragradient method reset

Status: **N=3 FINITE VIABILITY GATE RUNNING**

P4E targets a different mathematical object from P4D. Instead of differentiating aggregate exploitability, it estimates for every exact infoset the player's own conditional action advantage

`A(I) = E[u(STAY) - u(FOLD) | I, current opponents]`

and applies a projected predictor/corrector extragradient directly to the binary Nash complementarity conditions.

Implementation is in `src/deeppot/multiway_extragradient.py`. Regression tests compare sampled root action advantages against direct exact child-value differences and verify projection/simplex invariants. CI passed before the viability workflow was launched.

The complete finite protocol was frozen before results in `docs/P4E_PROJECTED_EXTRAGRADIENT_METHOD_RESET.md`:

- exactly N=3 rainbow `Ah 7d 2c` and monotone `Ah 7h 2h`;
- same exact CFR warm start: 250k x 3 seeds;
- exactly 64 extragradient rounds;
- 50k independent predictor samples/round;
- 50k independent corrector samples/round;
- normalized projected coordinate radius `0.10 / sqrt(round)`;
- original 250k-learn + 250k-holdout response gate;
- unchanged PASS threshold: every seat 95% unilateral-gain upper <= 0.03 ante;
- no early stopping, parameter tuning or checkpoint selection.

If both N=3 cases PASS, the method receives one predeclared N=4..8 scaling schedule and is then tested once on the already-defined rainbow/monotone representatives. If either N=3 case fails, P4E is BLOCKED and the method changes again; no P4E ladder is permitted.

P4 ends only with one frozen production method/configuration for every player-count mode N=2..8.

---

# P5 — Full exact production solve

Status: **NOT STARTED**

Prerequisites: P0, P3 and P4 PASS.

- [ ] enumerate all 1,755 canonical flops;
- [ ] solve N=2 through N=8 using the frozen per-mode production configuration;
- [ ] process flops independently with Ryzen-9 multiprocessing;
- [ ] checkpoint after every completed flop;
- [ ] resume cleanly after interruption;
- [ ] export exact policy + EV/reference metadata;
- [ ] hash every policy shard and final manifest;
- [ ] verify exactly 1,755 completed flop shards per supported player-count mode;
- [ ] no strategically lossy bucketing.

This is the only large production compute run. We do not launch a second complete solve unless a concrete bug invalidates the first.

---

# P6 — Operational policy compiler

Status: **NOT STARTED**

- [ ] define final key: economy profile | N | public scenario | canonical flop | exact hole-state ID;
- [ ] compile per-flop exact policies into compact binary lookup files;
- [ ] preserve the uncompressed mathematical source policies separately;
- [ ] store probabilities with enough precision that quantization changes no validated action materially;
- [ ] version/hash policy files;
- [ ] implement explicit MISS/unknown-state failure path;
- [ ] build a standalone lookup test utility.

Finite compiler gate: exhaustive key round-trip over every exported infoset once. PASS requires zero key/action mismatches.

---

# P7 — OpenHoldem / DeepPot runtime on the user's PC

Status: **NOT STARTED**

Reuse the proven DeepKK/OpenHoldem structure where applicable, but keep DeepPot as a separate runtime/profile.

- [ ] Pot Fold tablemap/scraper;
- [ ] detect dealt player count 2–8;
- [ ] detect BTN and fixed flop action order;
- [ ] detect prior FOLD/STAY history;
- [ ] read hero hole cards + flop;
- [ ] canonicalize exact runtime state identically to the solver;
- [ ] DLL/binary-policy lookup;
- [ ] output only FOLD or POT/STAY;
- [ ] HIT/MISS/state/action logs;
- [ ] fail closed on ambiguity;
- [ ] dedicated DeepPot OpenHoldem profile;
- [ ] Windows package/instructions for the user's machine.

---

# P8 — Finite shadow-mode gate

Status: **NOT STARTED**

Run DeepPot attached to the live table with **autoplayer disabled**.

Audit exactly **200 consecutive valid Pot Fold decisions**.

PASS requires:

- 200/200 correct player-count/BTN/history detections;
- 200/200 correct hero cards/flop recognition;
- 200/200 policy lookup HITs for supported states;
- zero illegal recommended actions;
- zero state-key mismatches in manual spot checks/log reconstruction.

If a concrete runtime bug appears, fix it and repeat the 200-decision gate **once**. Do not create successive shadow-test rounds for cosmetic differences.

---

# P9 — Autoplayer live gate and Base v1 release

Status: **NOT STARTED**

At the smallest practical Pot Fold stake:

- [ ] enable autoplayer;
- [ ] run exactly **200 valid decisions** under Base strategy;
- [ ] verify zero illegal/missed actions;
- [ ] verify runtime logs agree with actual table state;
- [ ] verify observed rake/payout still matches the frozen P0 economy profile;
- [ ] freeze and tag **DeepPot NLH Base v1**.

Profit/loss over 200 decisions is **not** a release criterion because short-run poker variance is not a software-correctness test.

## ROADMAP COMPLETE

When P9 passes, the requested objective is achieved: **the DeepPot IA is playing Pot Fold on the user's computer using the exact mathematical base strategy.**

---

# After Base v1 — separate, non-blocking roadmap

Only after the above is complete do we start the DeepKK-style exploitation layer:

`tracker/frame reconstructor -> aliases -> OpponentStats/PoolStats -> HU/VS1 exploit -> multiway exploit -> fallback to frozen Base v1`

PLO Pot Fold is also a separate post-Base-v1 project.