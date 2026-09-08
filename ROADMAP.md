# DeepPot NLH Base v1 — finite execution roadmap

## Definition of done

This roadmap ends when **DeepPot NLH Base v1 is playing Pot Fold on the user's computer through OpenHoldem**, using the mathematical base strategy only.

Base v1 must support 2–8 dealt players, preserve every strategically distinct flop+hole state modulo only exact global suit isomorphism, choose only FOLD or POT/STAY, use the frozen Pot Fold economy profile, log state/policy/action, fail closed on ambiguity, and pass the finite shadow/live gates below.

Opponent exploitation, tracker statistics and PLO are post-Base-v1 work and do not block this roadmap.

## Execution discipline — no infinite ladders

1. P0–P9 below are the complete path to Base v1.
2. We do not add iteration/sample rungs merely to improve a diagnostic number.
3. A frozen solver method that fails its declared gate is BLOCKED; we change method rather than retune that method after seeing results.
4. Regression tests are allowed only to protect concrete code/method changes and do not create new validation phases.
5. Cross-seed agreement is diagnostic; release quality is decided by exact-state coverage, independent response/EV quality and runtime correctness.
6. No strategically lossy card abstraction is planned for Base v1.

---

# P0 — Mechanics and economy freeze

Status: **MECHANICS COMPLETE / ECONOMY PENDING**

Completed mechanics:

- [x] equal ante from every dealt player;
- [x] no practical SB/BB forced-blind structure;
- [x] no preflop betting;
- [x] one flop FOLD or fixed POT/STAY decision street;
- [x] BTN acts last;
- [x] 2–8 dealt players;
- [x] automatic turn/river when 2+ players remain;
- [x] uncontested last-survivor terminal;
- [x] uncontested pots are raked.

Economy closure:

- [ ] freeze Pot Fold rake percentage/cap/rules for Base-v1 stake profile;
- [ ] freeze treatment of separately attributed reward/rakeback components;
- [ ] encode economy profile ID into every production manifest.

Finite evidence rule: use an official Pot-Fold-specific KKPoker schedule if one appears; otherwise use at most 12 clean live payout observations across useful pot/player geometries. Three current observations are mutually consistent with **2% of gross terminal pot**; cap/profile variation remains unresolved. See `docs/P0_ECONOMY_EVIDENCE.md`.

Engineering may continue under explicit provisional `provisional-2pct`. **P5 may not start until P0 PASS.**

---

# P1 — NLH game kernel

Status: **PASS**

- [x] card/deck model;
- [x] exact 2–8 player binary public action tree;
- [x] fixed STAY cost = initial ante pot;
- [x] BTN-last neutral action order;
- [x] uncontested/showdown terminals;
- [x] parameterized rake/cap;
- [x] ties and player utilities;
- [x] regression tests.

---

# P2 — Lossless state/equity representation

Status: **PASS**

- [x] 1,755 canonical NLH flops under global suit isomorphism;
- [x] **1,286,792** exact canonical `(flop, hero hole)` states;
- [x] per-flop dense exact hole-state indices;
- [x] dense public-history IDs for 2–8 players;
- [x] exact dense infoset keys;
- [x] exact 5/7-card evaluator and differential regression;
- [x] exact HU runout equity API;
- [x] multiway showdown evaluator.

The old `1,755 x 169` shorthand is not production-safe and is not used.

---

# P3 — Exact solver engine and throughput

Status: **PASS / CLOSED**

Implemented:

- [x] fixed-flop exact-state chance-sampled CFR+ candidate;
- [x] linear average strategy;
- [x] exact binary public-tree traversal;
- [x] dense integer infoset keys;
- [x] precomputed raw-hole -> exact-state map;
- [x] direct exact terminal evaluator;
- [x] one final-rank evaluation/player/deal reused across terminals;
- [x] reproducible seed policies/manifests;
- [x] exact consensus export;
- [x] multiprocessing for pilots and per-flop production;
- [x] checkpoint/resume;
- [x] shard/source/config/economy hashing;
- [x] exact-coverage enforcement.

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

No further throughput benchmark is planned.

---

# P4 — Finite solver-quality calibration

Status: **IN PROGRESS — HU PASS; multiway P4I RUNNING**

## P4A/P4B — HU: PASS / CLOSED

Frozen representative flops: rainbow `Ah 7d 2c`, two-tone `Ah 7h 2c`, monotone `Ah 7h 2h`, paired `Ah Ad 2c`.

HU gate:

- 100% exact coverage;
- pairwise greedy agreement >= 90%;
- each player unilateral-gain 95% upper <= 0.02 ante;
- total 95% upper <= 0.03 ante.

All four PASS after the single frozen 12-round bilateral response refinement. Provisional HU production method:

`2M x3 CFR consensus -> 12 x100k damped-response refinement`.

## Multiway gate

Representative textures for each N are rainbow `Ah 7d 2c` and monotone `Ah 7h 2h`. PASS requires 100% intended policy coverage and **every seat unilateral-gain 95% CI upper <= 0.030000 ante** under the independent split-sample response validator.

### P4C — CFR/FP: BLOCKED

All 12 raw N=3..8 cases failed. The one frozen 32-round FP correction on N=3..6 also failed. No more P4C tuning.

### P4D — FP-PED: BLOCKED

N=3 monotone passed; rainbow failed with worst upper `0.039123`. No more P4D tuning.

### P4E — projected Nash extragradient: BLOCKED

N=3 monotone passed; rainbow failed with seat uppers including `0.036877` and `0.033603`. No more P4E tuning.

### P4F — primal-dual worst-seat mirror-prox: BLOCKED

N=3 monotone passed; rainbow failed at seat 2 upper `0.039877`. P4F also exposed negative cross-sample internal gap estimates. No more P4F tuning.

### P4G — deterministic fixed-corpus worst-seat mirror-prox

Status: **N=3 PASS / N>=4 BLOCKED**

N=3 PASS:

- monotone uppers `0.007285, 0.009602, 0.011770`;
- rainbow uppers `0.021620, 0.022696, 0.029529`.

Frozen scaling then failed both N=4 and both N=5 cases, so P4G is not promoted beyond N=3. See `docs/P4G_SCALING_RESULT.md`.

### P4H — cyclic logit-response continuation: BLOCKED

Frozen N=4 run `34173556322` failed both textures:

- rainbow: `0.050204, 0.070360, 0.139722, 0.167616`;
- monotone: `0.015154, 0.017002, 0.041315, 0.076306`.

The final `tau=0.02` sweeps still had large policy movement, showing that the cyclic iteration had not reached its own numerical fixed point. See `docs/P4H_RESULT.md`. No more P4H sweeps/damping/temperature tuning.

### P4I — Anderson-accelerated QRE continuation: RUNNING

Method frozen before results in `docs/P4I_ANDERSON_QRE_METHOD_RESET.md`.

N=4 viability protocol:

- same CFR250k x3 -> FP32x50k -> PED32x50k -> P4G32x50k warm start;
- immutable P4I corpus 50k, seed `9912026`;
- simultaneous all-seat logit-response operator;
- temperatures `0.16 -> 0.08 -> 0.04 -> 0.02`;
- exactly 12 Type-II Anderson iterations per temperature;
- memory 5, ridge `1e-8`, Anderson/Picard blend 0.50;
- residual is diagnostic only;
- unchanged independent 250k learn + 250k holdout gate;
- no early stop, checkpoint selection, or post-result tuning.

Current run: **`34177615764`**.

Promotion rule:

- if both N=4 textures PASS, freeze N=5..8 P4I scaling before seeing any P4I N=5 result and execute once;
- if either fails, P4I is BLOCKED and the solver method changes again.

**P4 ends only when one frozen production method/configuration is accepted for every N=2..8.**

---

# P5 — Full exact production solve

Status: **NOT STARTED**

Prerequisites: **P0 PASS + P3 PASS + P4 PASS**.

- [ ] enumerate all 1,755 canonical flops;
- [ ] solve N=2..8 with frozen per-mode production configuration;
- [ ] run per-flop multiprocessing on Ryzen 9;
- [ ] checkpoint every completed flop and resume cleanly;
- [ ] export exact policy + EV/reference metadata;
- [ ] hash every shard and final manifest;
- [ ] verify exactly 1,755 completed shards per supported player-count mode;
- [ ] no strategically lossy bucketing.

This is the only planned full production solve unless a concrete bug invalidates it.

---

# P6 — Operational policy compiler

Status: **NOT STARTED**

- [ ] final key = economy profile | N | public scenario | canonical flop | exact hole-state ID;
- [ ] compile exact policies into compact binary lookup files;
- [ ] preserve mathematical source policies separately;
- [ ] precision/quantization check;
- [ ] version/hash output;
- [ ] explicit MISS/unknown-state path;
- [ ] standalone lookup tester.

Gate: exhaustive key round-trip once; **zero mismatches**.

---

# P7 — OpenHoldem / DeepPot runtime

Status: **NOT STARTED**

- [ ] Pot Fold tablemap/scraper;
- [ ] dealt-player count 2–8;
- [ ] BTN and action order;
- [ ] prior FOLD/STAY history;
- [ ] hero hole cards + flop;
- [ ] identical runtime canonicalization;
- [ ] DLL/binary-policy lookup;
- [ ] FOLD or POT/STAY output only;
- [ ] HIT/MISS/state/action logs;
- [ ] fail closed on ambiguity;
- [ ] dedicated DeepPot OpenHoldem profile;
- [ ] Windows package/instructions.

---

# P8 — Finite shadow-mode gate

Status: **NOT STARTED**

Attach to live Pot Fold with autoplayer disabled and audit exactly **200 consecutive valid decisions**.

PASS:

- 200/200 correct player-count/BTN/history detection;
- 200/200 correct hero cards/flop;
- 200/200 policy lookup HIT;
- zero illegal recommendations;
- zero state-key mismatches in reconstruction/manual checks.

A concrete runtime bug may be fixed and this 200-decision gate repeated **once**.

---

# P9 — Autoplayer live gate and Base v1 release

Status: **NOT STARTED**

At the smallest practical Pot Fold stake:

- [ ] enable autoplayer;
- [ ] exactly **200 valid decisions**;
- [ ] zero illegal/missed actions;
- [ ] runtime logs match table state;
- [ ] observed rake/payout remains consistent with frozen P0 profile;
- [ ] tag **DeepPot NLH Base v1**.

P/L over 200 decisions is not a release criterion.

## ROADMAP COMPLETE

P9 PASS means the requested objective is achieved: **DeepPot Base v1 is playing Pot Fold on the user's computer using the exact mathematical base strategy.**

---

# After Base v1 — non-blocking follow-on

Only after Base v1:

`tracker/frame reconstructor -> aliases -> OpponentStats/PoolStats -> HU/VS1 exploit -> multiway exploit -> fallback to frozen Base v1`

PLO Pot Fold is a separate later project.
