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

Status: **PASS / READY**

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
- [x] generated DeepPot mathematical TXT with one named STAY list per scenario;
- [x] Windows/Ryzen one-command launcher;
- [x] regression test proving compact audit produces the same final decisions as the row-form DeepKK-style evaluator.

Canonical production entry point:

`tools/run_deeppot_ryzen.ps1`

Guide: `docs/RYZEN_DEEPKK_PARITY_RUN.md`.

Frozen first-run budget:

- all N=2..8;
- all 1,755 flops;
- seed 123;
- 20,000 iterations/flop;
- 50,000 EV-audit samples/flop;
- minimum effective visits 25;
- CFR+ + linear average;
- `abs(EV_STAY-EV_FOLD)>CI95` for EV override;
- otherwise solver-average greedy fallback.

The exact strategy contains **635,675,248 decisions** across N=2..8. They are stored losslessly in bitsets instead of a 600M-row CSV/TXT.

---

# P4 — Official Ryzen mathematical-base run

Status: **READY TO START**

This is the direct DeepPot counterpart of the official DeepKK Ryzen run.

- [ ] execute `tools/run_deeppot_ryzen.ps1` on the Ryzen 9;
- [ ] complete all 1,755 flops for N=2..8;
- [ ] preserve every completed flop checkpoint;
- [ ] finish EV/CI audit for every flop;
- [ ] compile final/solver/confident/low-coverage bitsets;
- [ ] generate `DeepPot.txt` and `scenario_catalog_494.csv`;
- [ ] verify completed manifest and SHA256 hashes;
- [ ] review per-mode coverage/confidence summary once, without adding a new solver-method ladder.

Measured solver throughput implies about 127 aggregate CPU-hours for the solve portion at the frozen 20k budget. Parallel Ryzen execution should therefore be an hours-scale production job; audit and I/O add additional time.

If interrupted, rerun the exact same command and resume from checkpoints.

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

`DeepPot.txt` keeps DeepKK-like scenario/list organization. Exact list membership is stored in compiled bitsets because native OpenPPL handlists cannot encode flop-relative postflop state without losing information.

---

# P6 — Operational DeepPot / OpenHoldem

Status: **NOT STARTED**

Build the operational equivalent of DeepKK:

- [ ] dedicated Pot Fold tablemap/scraper;
- [ ] detect N=2..8;
- [ ] detect BTN and fixed action order;
- [ ] reconstruct prior FOLD/STAY history;
- [ ] identify one of the 494 public scenarios;
- [ ] read hero hole cards + flop;
- [ ] canonicalize to the exact same flop/hole key as the trainer;
- [ ] exact list membership lookup from the compiled mathematical bitsets/DLL;
- [ ] output only FOLD or POT/STAY;
- [ ] scenario/state/action logs;
- [ ] explicit HIT/MISS;
- [ ] fail closed on ambiguity;
- [ ] keep exploitation out of the Base.

The `.oppl/.txt` routing should resemble DeepKK as closely as OpenHoldem permits: explicit scenario functions and one base action route for each scenario.

---

# P7 — Compiler/lookup equivalence gate

Status: **NOT STARTED**

One exhaustive mathematical-to-runtime equivalence pass:

- [ ] every exported exact key resolves;
- [ ] mathematical action equals runtime action;
- [ ] zero unknown supported keys;
- [ ] zero action mismatches;
- [ ] runtime binary/DLL hash recorded.

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

---

# Archived research diagnostics

P4C, P4D, P4E, P4F, P4G, P4H and P4I remain in the repository for reproducibility only. P4I also completed and failed its former N=4 gate; that does not affect the DeepKK-parity production route.
