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

Status: **IN PROGRESS**

Already implemented:

- [x] fixed-flop exact-state chance-sampled CFR+ candidate;
- [x] linear average strategy;
- [x] full binary action-tree traversal per sampled deal;
- [x] dense integer infoset keys;
- [x] precomputed raw-hole -> exact-state map;
- [x] direct exact terminal evaluator;
- [x] reproducible manifests and seed policies;
- [x] cross-seed exact consensus-policy export;
- [x] multiprocessing across independent seeds for pilots.

Remaining production engineering:

- [ ] checkpoint/resume per canonical flop;
- [ ] resumable all-flop work queue;
- [ ] multiprocessing by canonical flop for the Ryzen 9;
- [ ] compact node storage if the N=5–8 benchmark shows RAM/throughput requires it;
- [ ] production manifest with source/economy/config hashes.

### One finite throughput benchmark

Run exactly one representative throughput benchmark per player count before the all-flop solve:

- N=2: 50k sampled deals;
- N=3: 20k;
- N=4: 10k;
- N=5: 5k;
- N=6: 2k;
- N=7: 1k;
- N=8: 500.

Use the max-state rainbow flop `Ah 7d 2c`. The purpose is runtime/RAM projection only, not strategy validation.

If projected production runtime or RAM is unacceptable, perform **one implementation optimization pass** and repeat this same benchmark once. No additional benchmark ladder is allowed.

---

# P4 — Finite solver-quality calibration

Status: **IN PROGRESS**

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

**No 5M/10M/etc A72r seed ladder will be added.** The next metric is unilateral response gain.

## P4B — HU response gate

- [x] implement split-sample unilateral best-response validator with independent holdout and 95% CI;
- [ ] validate the 2M x 3 consensus policy on A72r using exactly **250k learn + 250k holdout samples**;
- [ ] run the same 2M x 3 + response gate on exactly three additional representative flops:
  - `Ah 7h 2c` — two-tone;
  - `Ah 7h 2h` — monotone;
  - `Ah Ad 2c` — paired.

HU PASS criteria for each representative flop:

- exact infoset coverage = 100%;
- pairwise greedy agreement >= 90%;
- player-0 unilateral gain 95% upper bound <= **0.02 ante**;
- player-1 unilateral gain 95% upper bound <= **0.02 ante**;
- total response/NashConv gain 95% upper bound <= **0.03 ante**.

If one or more flops fail, make **one solver-method correction** targeted at response quality and rerun only the failing representative flop(s) once. If still failing, P4 is BLOCKED; do not add another iteration ladder.

## P4C — Multiway representative gate

After HU PASS, validate N=3..8 on exactly two representative textures each:

- `Ah 7d 2c` — max-state rainbow;
- `Ah 7h 2h` — low-state monotone.

For each N:

- [ ] train the fixed production candidate budget selected from P3/P4A calibration;
- [ ] require 100% intended exact-state coverage for the published policy;
- [ ] run one finite unilateral-response/robustness holdout audit per seat;
- [ ] record EV and response gain with confidence intervals.

Multiway response sample budget is fixed at:

- N=3–4: 250k learn + 250k holdout;
- N=5–8: 100k learn + 100k holdout.

PASS threshold: no seat may have unilateral gain 95% upper bound above **0.03 ante** on either representative texture.

As with HU, one solver-method correction + one rerun of failing cases is the maximum.

P4 ends with a single frozen solver configuration and production iteration budget for each player-count mode N=2..8.

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
