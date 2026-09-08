# DeepPot NLH — Roadmap

Reference date: 2026-09-08

## Definition of done

DeepPot is operational when OpenHoldem can map the real Pot Fold table state to one of the 494 exact public scenarios, canonicalize exact flop/hole cards, query an immutable strategy bit and execute FOLD or POT/STAY correctly.

Base v1 is frozen and already in live testing. A separate continuous CFR track now deepens the same exact game without strategic card abstraction.

Authoritative method lock: `docs/DEEPPOT_DEEPKK_METHOD_LOCK.md`.

Authoritative deep-training policy: `docs/CONTINUOUS_TRAINING_V2.md`.

---

# P0 — Mechanics and economy

Status: **MECHANICS COMPLETE / ECONOMY PROVISIONAL**

- [x] equal ante from every dealt player;
- [x] no preflop betting;
- [x] one flop FOLD or fixed POT/STAY decision street;
- [x] BTN last;
- [x] 2–8 dealt players;
- [x] automatic turn/river when 2+ remain;
- [x] uncontested last-survivor terminal;
- [x] uncontested pots raked;
- [ ] conclusively resolve cap/profile variation.

Base v1/deep track currently use `provisional-2pct-uncapped`.

---

# P1 — Exact game/state engine

Status: **PASS**

- [x] exact 2–8 player game tree;
- [x] parameterized rake/cap;
- [x] exact showdown evaluator;
- [x] 1,755 canonical flops;
- [x] 1,286,792 exact canonical `(flop, hero hole)` states;
- [x] dense exact hole-state IDs;
- [x] no equity/rank/draw bucketing;
- [x] exact terminal utilities.

---

# P2 — Complete public scenario catalogue

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

# P3/P4 — Base v1 production run

Status: **PASS / COMPLETE**

Frozen parameters:

- N=2..8;
- 1,755 flops/mode;
- seed 123;
- CFR+;
- linear average;
- 20,000 iterations/flop;
- 50,000 independent EV-audit samples/flop;
- audit min effective visits 25;
- 31 workers;
- 2% provisional uncapped rake.

Result:

- elapsed **6.28 h**;
- 635,675,248 exact final decisions;
- ~17.34 billion aggregate CFR node visits;
- ~27.28 average training visits per exact infoset;
- audit low coverage 81.7182%;
- confident 10.1193% of all states;
- final STAY 38.6442%.

Conclusion: Base v1 is complete and usable, but per-state training depth is materially lower than DeepKK. This motivates the separate continuous deep track; it does not invalidate the frozen Base v1.

---

# P5 — Immutable Base v1 freeze

Status: **PASS / FROZEN**

Freeze SHA256:

`4d4077796ce81ec4d74a99818d69cc999221ad77c973c7d6fe7d4102d1a43a8a`

- [x] mathematical run frozen;
- [x] final/solver/confidence/low-coverage vectors frozen;
- [x] scenario catalogue frozen;
- [x] exact indexes frozen;
- [x] runtime package frozen;
- [x] P5 freeze manifest created.

Never overwrite Base v1 with deeper outputs.

---

# P6 — OpenHoldem exact runtime

Status: **OFFLINE CORE PASS / LIVE TESTING ON i5**

- [x] one `dll$deeppot_action` query;
- [x] exact 494-scenario mapping;
- [x] exact N2..N8 bit lookup;
- [x] exact Python/C++ canonicalization regression;
- [x] DeepKK-like operational TXT;
- [x] Win32 `user.dll` build;
- [x] fail-closed zero on invalid state;
- [x] deterministic HIT/MISS logs;
- [x] correct OpenHoldem suit mapping H/D/C/S `0/1/2/3` -> DeepPot C/D/H/S `0/1/2/3` via `[2,1,0,3]`;
- [x] correct prior-action fallback when `foldbits2` omits a folded actor but `playersplayingbits` shows the actor no longer playing;
- [ ] continue live i5 observation for scraper/history edge cases;
- [ ] finish tablemap-specific `negative potcommon` cleanup if operationally relevant.

Machine split:

- Ryzen 9 = solving/training/build computation;
- i5 = KKPoker/OpenHoldem live testing.

---

# P7 — Mathematical -> runtime equivalence

Status: **PASS / CLOSED**

- [x] all 635,675,248 exact infosets structurally resolvable;
- [x] unknown supported keys = 0;
- [x] action bit mismatches = 0;
- [x] index metadata mismatches = 0;
- [x] source/runtime SHA256 identical per N.

---

# P8/P9 — Live Base v1 validation

Status: **IN PROGRESS ON i5**

The user elected to follow the practical DeepKK-style route rather than make a separate shadow/debug phase mandatory. Runtime logs are still used diagnostically.

- [x] Base v1 loaded through functional `DeepPot.txt` + `user.dll` + `DeepPotRuntime`;
- [x] real HIT decisions observed;
- [x] suit-decoding bug found/fixed from live log;
- [x] prior FOLD/STAY reconstruction edge case found/fixed from live log;
- [ ] continue normal play/test sample and inspect any questionable action or MISS;
- [ ] confirm no remaining systematic runtime mapping error;
- [ ] preserve targeted questionable-hand review separately from solver retraining.

---

# D1 — Continuous exact CFR infrastructure

Status: **IMPLEMENTED / PRE-RUN VALIDATION**

Goal: one long mathematical trajectory that can be interrupted, snapshotted and resumed without losing accumulated CFR state.

- [x] add `continue_solve` with correct global linear-average iteration offset;
- [x] persist both regrets per infoset;
- [x] persist both linear-average strategy sums per infoset;
- [x] persist exact visit count per infoset;
- [x] persist completed iteration count;
- [x] persist exact RNG state;
- [x] source/config provenance lock;
- [x] atomic task-state replacement;
- [x] 12,285 task scheduler (7 modes × 1,755 flops);
- [x] interleave N2..N8 by flop for balanced arbitrary-time snapshots;
- [x] 50,000-iteration default checkpoint chunks;
- [x] use frozen 31-worker benchmark;
- [x] graceful Ctrl+C drain + `SAFE TO CLOSE`;
- [x] same-command exact resume;
- [x] record worker errors as manifest stage `error` before raising;
- [x] initial 30 GiB free-space gate;
- [x] resumed-session 2 GiB working-space gate;
- [x] dependency-free exact-resume smoke script;
- [ ] CI green on the finalized infrastructure;
- [ ] Ryzen smoke PASS;

Estimated persistent state: **~21.31 GiB** plus small metadata/snapshot overhead.

---

# D2 — Deep training target

Status: **NOT STARTED**

Frozen first major target:

> **all 635,675,248 exact infosets must reach `visit_count >= 1000`.**

This replaces the vague “15 days” concept. Calendar time is only an estimate.

- [ ] start `runs\continuous_master` on Ryzen;
- [ ] keep CFR+ / linear average / seed123 / 2% provisional uncapped economy;
- [ ] monitor exact min/p1/p5/median/mean/p95/max visit depth;
- [ ] stop automatically only when every task's minimum reaches target;
- [ ] if policy still changes materially at 1,000, continue same master deeper rather than restart.

`1000` is a pragmatic target, not a proof of optimality.

---

# D3 — Arbitrary-time snapshots

Status: **IMPLEMENTED / WAITING FOR MASTER**

The user may safely pause and create a playable snapshot at any point after all 12,285 tasks have at least one persisted state.

Suggested labels:

- `V1.1` around ~5 days;
- `V1.2` around ~10 days;
- `V2` at the 1,000-minimum completion gate.

The day counts are not quality gates.

Each snapshot:

- [x] leaves the master CFR state untouched;
- [x] creates exact current N2..N8 greedy linear-average bitsets;
- [x] reuses the validated runtime index;
- [x] creates `DeepPot_<snapshot>.txt`;
- [x] records exact visit distribution;
- [x] records near-50/50 average-policy fraction;
- [x] compares every action bit with the previous snapshot globally/per N;
- [x] can be followed by immediate resume of the same master.

---

# D4 — Deep-track validation policy

Status: **LOCKED**

No mandatory global EV/CI audit is required for every deep snapshot.

Primary validation:

- real training visit depth;
- preserved regret/strategy-sum diagnostics;
- exact policy stability V1.1 -> V1.2 -> V2;
- per-N concentration of changed actions;
- near-50/50 average-policy concentration.

Independent EV audit remains **optional and targeted** for suspicious states or if convergence evidence is ambiguous.

If action stability remains material at 1,000 visits, deepen the same trajectory to a justified higher target.

---

# Immediate next gate

Before starting the multi-day Ryzen run:

1. repository CI must be green;
2. Ryzen must run `python C:\DeepPot\tools\check_deeppot_continuous_resume.py` and return PASS;
3. confirm disk safety;
4. then start `tools\run_deeppot_continuous.ps1`.

## ROADMAP CURRENT
