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
3. A failed frozen method/gate is marked BLOCKED; we change the method instead of tuning the same method indefinitely.
4. New unit/regression tests are allowed only to protect a concrete bug fix or roadmap feature; they do not create validation phases.
5. Cross-seed probability agreement is diagnostic. Release quality is decided primarily by exact-state coverage, independent unilateral-response quality and runtime correctness.
6. Strategic card abstraction is not planned for Base v1. Exact global suit isomorphism is the only card-state reduction.
7. Every new solver-method reset must be frozen before observing its acceptance result.

---

# P0 — Mechanics and economy freeze

Status: **MECHANICS COMPLETE / ECONOMY PENDING**

Completed mechanics:

- [x] equal ante from every dealt player;
- [x] no practical SB/BB forced-blind payments;
- [x] preflop skipped;
- [x] one flop decision street;
- [x] FOLD or fixed POT/STAY action;
- [x] BTN last to act;
- [x] 2–8 dealt players;
- [x] automatic turn/river after flop action when 2+ remain;
- [x] uncontested terminal when everyone before the last survivor folds;
- [x] uncontested pots are raked.

Economy closure:

- [ ] freeze Pot Fold rake percentage/cap/rules for the Base-v1 stake/profile;
- [ ] freeze whether any separately attributed reward/rakeback enters decision EV;
- [ ] encode economy profile ID into every production policy manifest.

Finite evidence rule: use a Pot-Fold-specific official KKPoker schedule if one becomes available. Otherwise use **at most 12 clean live payout observations** across relevant player-count/pot geometries. The three current observations are mutually consistent with **2% of gross terminal pot**; the remaining uncertainty is mainly cap/profile variation. Engineering may continue under explicit provisional profile `provisional-2pct`, but P5 waits for P0 PASS.

---

# P1 — NLH game kernel

Status: **PASS**

- [x] card/deck model;
- [x] exact 2–8 player Pot Fold public tree;
- [x] fixed STAY cost = initial ante pot;
- [x] BTN-last neutral action order;
- [x] uncontested/showdown terminals;
- [x] parameterized rake/cap;
- [x] ties and per-player utilities;
- [x] regression tests.

---

# P2 — Lossless card/state representation

Status: **PASS**

- [x] 1,755 canonical NLH flops under global suit isomorphism;
- [x] exact flop+hole canonicalization;
- [x] **1,286,792** exact `(canonical flop, hero hole)` states;
- [x] exact per-flop dense hole-state IDs;
- [x] public history IDs for 2–8 players;
- [x] dense exact infoset keys;
- [x] exact direct 7-card evaluator + differential regression;
- [x] exact HU runout equity;
- [x] exact multiway showdown evaluator.

The old `1,755 x 169` shorthand is not production-safe and is not used.

---

# P3 — Exact solver engine and throughput gate

Status: **PASS / CLOSED**

Implemented:

- [x] exact-state fixed-flop chance-sampled CFR+ candidate;
- [x] linear average strategy;
- [x] full binary action-tree traversal;
- [x] dense integer infosets;
- [x] precomputed raw-hole -> exact-state map;
- [x] terminal hand-rank reuse;
- [x] reproducible seed policies and consensus export;
- [x] multiprocessing across seeds;
- [x] checkpoint/resume per canonical flop;
- [x] resumable all-flop queue;
- [x] multiprocessing by flop for Ryzen 9;
- [x] policy/source/config/economy hashes and atomic manifest updates;
- [x] exact-coverage enforcement before publication.

Frozen post-optimization throughput on `Ah 7d 2c`:

| N | iterations/s | infoset-visits/s |
|---:|---:|---:|
| 2 | 11,806 | 23,612 |
| 3 | 5,557 | 33,342 |
| 4 | 2,659 | 37,224 |
| 5 | 1,314 | 39,429 |
| 6 | 638 | 39,536 |
| 7 | 309 | 38,940 |
| 8 | 146.6 | 37,243 |

**No further throughput ladder.**

---

# P4 — Finite strategy-quality calibration

Status: **IN PROGRESS — HU PASS / N3 METHOD FROZEN / N>=4 P4H RUNNING**

Acceptance principle for multiway: 100% intended exact-state coverage and every seat unilateral-gain 95% CI upper <= **0.030000 ante** on an independent split-sample response audit.

## P4A/P4B — HU: PASS / CLOSED

Frozen representative HU textures all pass after the single allowed response-directed correction. Production method under provisional economy:

`2M x 3 CFR consensus -> fixed 12 x 100k damped bilateral response refinement`.

No further HU ladder.

## P4C — CFR/FP: BLOCKED

All 12 raw N=3..8 representative cases failed. The one frozen FP correction on N=3..6 also failed all eight corrected cases. No more P4C tuning.

## P4D — FP-PED: BLOCKED

N=3 monotone passed, rainbow failed (`seat2 upper 0.039123`). No more P4D tuning.

## P4E — projected Nash extragradient: BLOCKED

N=3 monotone passed; rainbow failed (`seat0 0.036877`, `seat2 0.033603`). No more P4E tuning.

## P4F — primal-dual worst-seat mirror-prox: BLOCKED

N=3 monotone passed; rainbow failed (`seat2 0.039877`). P4F also exposed cross-sample negative-gap/seat-weighting mismatch. No more P4F tuning.

## P4G — deterministic fixed-corpus worst-seat mirror-prox

Status: **N=3 PASS / N>=4 BLOCKED**

Frozen N=3 results:

| flop | seat 0 | seat 1 | seat 2 | result |
|---|---:|---:|---:|---|
| monotone `Ah 7h 2h` | 0.007285 | 0.009602 | 0.011770 | PASS |
| rainbow `Ah 7d 2c` | 0.021620 | 0.022696 | 0.029529 | PASS |

Therefore P4G is the currently frozen candidate for **N=3**.

The predeclared scaling gate then failed both completed N=4 and N=5 textures:

| case | worst seat 95% upper | result |
|---|---:|---|
| N4 rainbow | 0.075952 | FAIL |
| N4 monotone | 0.036477 | FAIL |
| N5 rainbow | 0.190325 | FAIL |
| N5 monotone | 0.104327 | FAIL |

Hence P4G is **BLOCKED for N>=4**. Remaining already-running N6..8 jobs are diagnostic only and cannot reopen P4G. See `docs/P4G_SCALING_RESULT.md`.

## P4H — deterministic cyclic logit-response continuation

Status: **N=4 FROZEN VIABILITY GATE RUNNING**

Method reset frozen before results in `docs/P4H_LOGIT_CONTINUATION_METHOD_RESET.md`.

Core change:

- solve local behavioral Nash fixed-point equations directly rather than minimizing aggregate exploitability gradients;
- use one immutable P4H chance corpus;
- estimate exact-infoset conditional `A(I)=EV(STAY)-EV(FOLD)`;
- cyclic Gauss-Seidel seat updates in reverse action order, BTN to first actor;
- logit response continuation temperatures `0.16 -> 0.08 -> 0.04 -> 0.02` ante;
- exactly 12 full reverse-seat sweeps per temperature;
- damping 0.50;
- P4G final policy is the fixed warm start;
- no early stopping, checkpoint selection, texture-specific settings or parameter sweep;
- final gate remains independent 250k learn + 250k holdout for N=4.

Current N=4 workflow: `34173556322`.

Promotion rule:

- if both N=4 textures PASS, freeze N=5..8 P4H scaling schedule before observing any P4H N=5 result and execute the eight remaining cases once;
- if either N=4 texture FAILS, P4H is BLOCKED and we change method rather than tune P4H.

P4 is complete only when one frozen production method/configuration is available for every N=2..8.

---

# P5 — Full exact production solve

Status: **NOT STARTED**

Prerequisites: **P0 PASS + P3 PASS + P4 PASS**.

- [ ] enumerate all 1,755 canonical flops;
- [ ] solve N=2..8 with the frozen per-mode production methods/configurations;
- [ ] process flops independently with Ryzen-9 multiprocessing;
- [ ] checkpoint every completed flop and resume cleanly;
- [ ] export exact policy + EV/reference metadata;
- [ ] hash every policy shard and final manifest;
- [ ] verify exactly 1,755 completed flop shards per player-count mode;
- [ ] no strategically lossy bucketing.

This is the only full production solve unless a concrete bug invalidates it.

---

# P6 — Operational policy compiler

Status: **NOT STARTED**

- [ ] final key: economy profile | N | public scenario | canonical flop | exact hole-state ID;
- [ ] compile exact policies into compact binary lookup files;
- [ ] preserve uncompressed mathematical source policies;
- [ ] retain enough numeric precision that quantization does not materially change validated actions;
- [ ] version/hash all policy files;
- [ ] explicit MISS/unknown-state failure path;
- [ ] standalone lookup test utility.

Finite gate: exhaustive round-trip over every exported infoset once; zero key/action mismatches required.

---

# P7 — OpenHoldem / DeepPot runtime on the user's PC

Status: **NOT STARTED**

Reuse proven DeepKK/OpenHoldem infrastructure where appropriate, but keep DeepPot separate.

- [ ] Pot Fold tablemap/scraper;
- [ ] detect dealt player count 2–8;
- [ ] detect BTN and action order;
- [ ] detect prior FOLD/STAY history;
- [ ] read hero hole cards + flop;
- [ ] canonicalize runtime state identically to solver;
- [ ] binary-policy/DLL lookup;
- [ ] output only FOLD or POT/STAY;
- [ ] HIT/MISS/state/action logs;
- [ ] fail closed on ambiguity;
- [ ] dedicated DeepPot OpenHoldem profile;
- [ ] Windows package and instructions.

---

# P8 — Finite shadow-mode gate

Status: **NOT STARTED**

Attach DeepPot to live Pot Fold with autoplayer disabled and audit exactly **200 consecutive valid decisions**.

PASS requires:

- 200/200 correct player-count/BTN/history detections;
- 200/200 correct hero cards/flop recognition;
- 200/200 policy lookup HITs;
- zero illegal recommended actions;
- zero state-key mismatches in manual/log reconstruction.

If a concrete runtime bug appears, fix it and repeat the 200-decision gate **once**. No successive cosmetic shadow rounds.

---

# P9 — Autoplayer live gate and Base v1 release

Status: **NOT STARTED**

At the smallest practical Pot Fold stake:

- [ ] enable autoplayer;
- [ ] run exactly **200 valid decisions** under Base strategy;
- [ ] verify zero illegal/missed actions;
- [ ] verify runtime logs agree with actual table state;
- [ ] verify observed rake/payout still matches frozen P0 profile;
- [ ] freeze and tag **DeepPot NLH Base v1**.

Profit/loss over 200 decisions is not a release criterion.

## ROADMAP COMPLETE

P9 PASS means the requested Base-v1 objective is achieved: **DeepPot is playing Pot Fold on the user's computer using the frozen exact mathematical base strategy.**

---

# After Base v1 — separate non-blocking roadmap

Only after Base v1:

`tracker/frame reconstructor -> aliases -> OpponentStats/PoolStats -> HU/VS1 exploit -> multiway exploit -> fallback to frozen Base v1`

PLO Pot Fold is also separate.
