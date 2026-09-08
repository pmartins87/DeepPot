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

Three live observations are consistent with **2% of gross terminal pot**. Cap/profile variation remains unconfirmed. The first production run records the explicit profile `provisional-2pct-uncapped`; final Base-v1 tagging still requires the live economy to remain consistent or the affected profile to be regenerated.

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

Every nonterminal public FOLD/STAY history is explicitly enumerated. The BTN all-prior-FOLD history is terminal and has no decision.

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

Frozen production budget: N=2..8, all 1,755 flops, seed 123, 20,000 iterations/flop, 50,000 EV-audit samples/flop, minimum effective visits 25, CFR+ + linear average, confident EV-best else solver-average greedy fallback, **31 workers**.

The exact strategy contains **635,675,248 decisions** across N=2..8, stored losslessly as bitsets.

---

# P4 — Official Ryzen mathematical-base run

Status: **RUNNING ON TARGET RYZEN — 31 WORKERS**

Worker calibration is closed: 31 workers won the frozen 15/23/31 one-pass benchmark and no further tuning will be performed.

Production run:

- [x] start `tools/run_deeppot_ryzen.ps1` on the target Ryzen 9;
- [ ] complete all 1,755 flops for each N=2..8;
- [ ] preserve every completed flop checkpoint;
- [ ] finish EV/CI audit for every flop;
- [ ] compile final/solver/confident/low-coverage bitsets;
- [ ] generate `DeepPot.txt` and `scenario_catalog_494.csv`;
- [ ] verify completed manifest and SHA256 hashes;
- [ ] review per-mode coverage/confidence summary once, without adding a new solver-method ladder.

The running local output root is `C:\DeepPot\runs\deepkk_parity_full`. If interrupted, rerunning the same command resumes valid checkpoints.

---

# P5 — Immutable mathematical source freeze

Status: **AWAITS P4 OUTPUT**

Freeze and preserve:

- `DeepPot.txt`;
- 494-scenario catalogue;
- N2..N8 final exact STAY/FOLD bitsets;
- solver-greedy bitsets;
- confidence/low-coverage bitsets;
- N2..N8 exact indexes;
- audit summaries;
- run manifest;
- source/config/economy SHA256 hashes.

---

# P6 — Operational DeepPot / OpenHoldem

Status: **IN PROGRESS IN PARALLEL WITH P4**

Offline/runtime-independent work already implemented:

- [x] one signed `dll$deeppot_action` contract covering all 494 scenarios;
- [x] exact runtime scenario mapping identical to trainer scenario IDs;
- [x] mathematical-run -> minimal live-runtime package compiler;
- [x] portable binary runtime index for all canonical flops;
- [x] final N2..N8 exact STAY/FOLD bitset loader;
- [x] exact 24-suit-permutation flop/hole canonicalization in C++;
- [x] exact flop-relative hole-state ID reconstruction in C++;
- [x] exact strategy bit lookup in C++;
- [x] Python-reference vs C++ exact-state lookup regression test;
- [x] generator for a DeepKK-like operational TXT with 494 explicit `f$sit_*` functions and 494 explicit `f$list_*_STAY` membership functions;
- [x] OpenHoldem user.dll adapter source with deterministic HIT/MISS logging and fail-closed result 0;
- [x] normalize OpenHoldem suit symbols 1..4 to DeepPot c/d/h/s indices 0..3;
- [x] isolated OpenHoldem integration branch `deeppot_runtime_v1` in `pmartins87/myoh_private`;
- [x] deterministic Win32 user.dll build gate created on that isolated branch;
- [x] post-P4 runtime package builder `tools/build_deeppot_runtime.ps1`;
- [x] operational architecture documented in `docs/P6_OPENHOLDEM_RUNTIME.md`.

Still live-dependent / not yet accepted:

- [ ] successful actual Win32 `user.dll` build artifact from the isolated OpenHoldem branch;
- [ ] dedicated Pot Fold tablemap/scraper;
- [ ] validate KKPoker chair numbering and BTN-to-last action-order reconstruction against the live table;
- [ ] validate `playersdealtbits` / `playersplayingbits` / `foldbits2` as the exact FOLD/STAY-history source on Pot Fold;
- [ ] validate the actual STAY/POT button action mapping; `BetPot` remains a disabled placeholder until then;
- [ ] generate final operational formula with the completed runtime-manifest hash;
- [ ] keep `f$deeppot_live_enabled=false` until shadow validation;
- [ ] keep exploitation out of Base v1.

The operational `.txt` deliberately resembles DeepKK: explicit situation routing plus one logical STAY list per situation. Only the physical list membership lookup differs because native OpenPPL 169-hand lists cannot encode exact flop-relative states.

---

# P7 — Compiler/lookup equivalence gate

Status: **FOUNDATION IMPLEMENTED / FULL PASS AWAITS P4 OUTPUT**

One exhaustive mathematical-to-runtime equivalence pass:

- [ ] every exported exact key resolves;
- [ ] mathematical action equals runtime action;
- [ ] zero unknown supported keys;
- [ ] zero action mismatches;
- [ ] runtime binary/DLL hash recorded.

The Python/C++ one-state regression already protects canonicalization/ID parity; the exhaustive all-key pass waits for the completed P4 base.

---

# P8 — Shadow live gate

Status: **NOT STARTED**

Audit exactly **200 consecutive valid decisions** with autoplayer disabled.

PASS requires correct N/scenario/cards/flop/key lookup and no illegal recommendation. Repeat once only after a concrete runtime bug fix.

---

# P9 — Autoplayer live gate / Base v1

Status: **NOT STARTED**

At the smallest practical Pot Fold stake:

- [ ] exactly 200 valid live decisions;
- [ ] zero illegal/missed actions;
- [ ] logs match table state;
- [ ] payouts/rake remain consistent with the Base-v1 economy profile;
- [ ] tag **DeepPot NLH Base v1**.

Profit/loss over these 200 decisions is not a release criterion.

## ROADMAP COMPLETE

After P9, begin the DeepKK-style tracking/exploitation layer with hard fallback to frozen DeepPot Base v1.
