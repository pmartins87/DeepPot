# DeepPot NLH Base v1 — DeepKK-parity roadmap

## Definition of done

DeepPot Base v1 is complete when it is playing Pot Fold through OpenHoldem on the user's computer using one immutable mathematical base strategy and no opponent exploitation.

Production method is locked to DeepKK:

`enumerate scenarios -> CFR+ -> linear average -> EV/CI95 audit -> immutable exact lists -> OpenHoldem operational layer -> finite runtime validation`

Authoritative method lock: `docs/DEEPPOT_DEEPKK_METHOD_LOCK.md`.

The P4C..P4I exploitability/fixed-point experiments are archived diagnostics, not release blockers. There is no P4J/P4K chain.

---

# P0 — Mechanics and economy

Status: **MECHANICS COMPLETE / ECONOMY PROVISIONAL**

Confirmed mechanics:

- equal ante from every dealt player;
- no preflop betting;
- one flop FOLD or fixed POT/STAY decision street;
- BTN last;
- 2–8 dealt players;
- automatic turn/river when 2+ remain;
- uncontested last-survivor terminal;
- uncontested pots are raked.

Three live observations are consistent with **2% of gross terminal pot**. Cap/profile variation remains unconfirmed. Base v1 records `provisional-2pct-uncapped` and the live shadow/autoplayer gates continue checking economic consistency.

---

# P1 — Exact game/state engine

Status: **PASS**

- [x] exact 2–8 player game tree;
- [x] parameterized rake/cap;
- [x] exact showdown evaluator;
- [x] 1,755 canonical flops;
- [x] 1,286,792 exact canonical `(flop, hero hole)` states;
- [x] dense per-flop hole-state IDs;
- [x] dense public-scenario IDs;
- [x] exact terminal utilities;
- [x] no strategic 169-only postflop abstraction.

---

# P2 — Complete scenario catalogue

Status: **PASS**

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

---

# P3 — DeepKK-parity generator/package

Status: **PASS / CLOSED**

Implemented:

- [x] CFR+ exact-state solver;
- [x] linear average;
- [x] deterministic seed/config/source hashes;
- [x] multiprocessing by canonical flop;
- [x] per-flop checkpoint/resume;
- [x] DeepKK-style EV(FOLD) vs EV(STAY) audit;
- [x] standard error + CI95;
- [x] minimum effective visits;
- [x] confident EV-best action;
- [x] inconclusive-state fallback to solver-average greedy action;
- [x] compact lossless bitset output;
- [x] 494-scenario catalogue;
- [x] Windows/Ryzen one-command launcher;
- [x] one finite local worker-count benchmark.

Frozen Base-v1 budget: N=2..8, all 1,755 flops, seed 123, 20,000 iterations/flop, 50,000 EV-audit samples/flop, minimum effective visits 25, CFR+ + linear average, confident EV-best else solver-average greedy fallback, 31 workers.

---

# P4 — Official Ryzen mathematical-base run

Status: **PASS / COMPLETE**

- [x] complete all 1,755 flops for N=2..8;
- [x] preserve checkpoints;
- [x] finish EV/CI audit;
- [x] compile final/solver/confident/low-coverage bitsets;
- [x] generate `DeepPot.txt` and `scenario_catalog_494.csv`;
- [x] verify completed manifest and hashes;
- [x] review aggregate/per-mode confidence and coverage once.

Result:

- elapsed: **22,598.7 s = 6.28 h**;
- exact decisions: **635,675,248**;
- coverage at least once: **100.0000%**;
- low effective-audit coverage: **81.7182%**;
- confident: **10.1193% of all states / 55.3521% of adequately covered states**;
- final STAY: **38.6442%**;
- confident EV overrides: **8,307,288**.

Low coverage affects independent audit confidence, not existence of CFR/final actions. Base v1 proceeds to runtime validation while deeper statistical work is isolated as a future Base-v2 candidate.

---

# P5 — Immutable mathematical source freeze

Status: **PASS / FROZEN**

- [x] `DeepPot.txt`;
- [x] 494-scenario catalogue;
- [x] N2..N8 final exact STAY/FOLD bitsets;
- [x] solver-greedy bitsets;
- [x] confidence/low-coverage bitsets;
- [x] N2..N8 exact indexes;
- [x] audit summaries;
- [x] run manifest;
- [x] runtime package;
- [x] immutable P5 freeze manifest.

Freeze manifest:

`C:\DeepPot\runs\p5_freeze\P5_FREEZE_MANIFEST.json`

SHA256:

`4d4077796ce81ec4d74a99818d69cc999221ad77c973c7d6fe7d4102d1a43a8a`

Base v1 must never be overwritten by later deeper training.

---

# P6 — Operational DeepPot / OpenHoldem

Status: **OFFLINE CORE PASS / LIVE SCRAPE VALIDATION PENDING**

- [x] one signed `dll$deeppot_action` contract covering all 494 scenarios;
- [x] exact runtime scenario mapping identical to trainer IDs;
- [x] mathematical-run -> minimal runtime compiler;
- [x] binary runtime index for all canonical flops;
- [x] final N2..N8 exact bitset loader;
- [x] exact canonicalization and hole-state reconstruction in C++;
- [x] exact strategy bit lookup in C++;
- [x] Python vs C++ exact-state regression;
- [x] DeepKK-like operational TXT generator;
- [x] OpenHoldem adapter with deterministic HIT/MISS logging and fail-closed 0;
- [x] OpenHoldem suit normalization;
- [x] isolated OpenHoldem branch `deeppot_runtime_v1`;
- [x] successful Win32 Release `user.dll` build;
- [x] official runtime package compiled;
- [x] no-action shadow formula generator and package builder.

Still live-dependent:

- [ ] validated Pot Fold tablemap/scraper;
- [ ] validate KKPoker chair numbering and BTN-last order;
- [ ] validate `playersdealtbits` / `playersplayingbits` / `foldbits2` against actual prior FOLD/STAY history;
- [ ] validate the real STAY/POT click mapping;
- [ ] keep exploitation out of Base v1.

---

# P7 — Compiler/lookup equivalence gate

Status: **PASS / CLOSED**

Local exhaustive result:

`C:\DeepPot\runs\p7_equivalence\P7_EQUIVALENCE_RESULT.json`

- [x] all **635,675,248** exported exact infosets structurally resolvable;
- [x] unknown supported keys = **0**;
- [x] action bit mismatches = **0**;
- [x] index metadata mismatches = **0**;
- [x] source/runtime final SHA256 identical for N2..N8;
- [x] canonical flop-code and per-flop hole-state widths checked;
- [x] source/runtime action vectors XOR-compared byte-for-byte.

---

# P8 — Shadow live gate

Status: **READY FOR TABLEMAP/STATE SETUP**

Preparation:

- [x] create no-action shadow formula `DeepPot_SHADOW_SAFE.txt`;
- [x] create `tools/prepare_deeppot_shadow.ps1`;
- [ ] install validated Pot Fold tablemap;
- [ ] place compiled DeepPot `user.dll` beside `DeepPotRuntime`;
- [ ] load shadow formula;
- [ ] keep Autoplayer OFF;
- [ ] Formula Editor -> Debug -> Auto to query/log `dll$deeppot_action` once per heartbeat;
- [ ] first validate cards/N/BTN/chairs/FOLD-STAY history and HIT/MISS behavior;
- [ ] then audit exactly **200 consecutive valid decisions**.

PASS requires correct N/scenario/cards/flop/key lookup and no illegal recommendation. Repeat once only after a concrete runtime bug fix.

---

# P9 — Autoplayer live gate / Base v1

Status: **NOT STARTED**

At the smallest practical Pot Fold stake:

- [ ] validate actual STAY/POT action mapping before enabling clicks;
- [ ] exactly 200 valid live decisions;
- [ ] zero illegal/missed actions;
- [ ] logs match table state;
- [ ] payouts/rake remain consistent with the Base-v1 economy profile;
- [ ] tag **DeepPot NLH Base v1**.

Profit/loss over these 200 decisions is not a release criterion.

## Parallel Base-v2 depth track

Base v1 proceeds to P8/P9 unchanged. In parallel, prepare a separate deeper audit/training campaign with substantially stronger statistical coverage. Never mutate or silently replace the frozen Base-v1 artifacts.

## ROADMAP COMPLETE
