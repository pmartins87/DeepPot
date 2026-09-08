# DeepPot NLH Base v1 — DeepKK-parity roadmap

## Definition of done

This roadmap ends when **DeepPot NLH Base v1 is playing Pot Fold on the user's computer through OpenHoldem**, using one immutable mathematical base strategy and no opponent exploitation.

The production philosophy is now explicitly locked to the method that produced DeepKK:

`enumerate scenarios -> CFR+ base solve -> linear average -> EV/CI audit -> immutable mathematical TXT/CSV -> operational OpenHoldem layer -> runtime validation`

See `docs/DEEPPOT_DEEPKK_METHOD_LOCK.md`.

The P4C..P4I solver experiments are preserved as research history, but are **not release blockers** and do not create a P4J/P4K chain.

---

# P0 — Mechanics and economy

Status: **MECHANICS COMPLETE / ECONOMY PENDING FINAL FREEZE**

Confirmed mechanics:

- equal ante from every dealt player;
- no preflop betting;
- one flop decision street;
- only FOLD or fixed POT/STAY;
- BTN last;
- 2–8 dealt players;
- automatic turn/river when 2+ remain;
- last-survivor uncontested terminal;
- uncontested pots are raked.

Current evidence is consistent with **2% of gross terminal pot**. Cap/profile variation remains the unresolved item. Engineering may use explicit provisional `provisional-2pct`; the official immutable run must record the economy actually frozen for the intended live stake.

---

# P1 — Exact game/state engine

Status: **PASS**

- [x] exact 2–8 player Pot Fold game tree;
- [x] parameterized rake/cap;
- [x] exact showdown evaluator;
- [x] 1,755 canonical flops under global suit isomorphism;
- [x] 1,286,792 exact canonical `(flop, hero hole)` states;
- [x] dense exact per-flop hole-state IDs;
- [x] dense scenario IDs;
- [x] exact terminal utilities.

No 169-only postflop abstraction is used because the visible flop changes the strategic meaning of suits/ranks.

---

# P2 — Complete scenario catalogue

Status: **PASS / IMPLEMENTED**

DeepKK enumerated every AoF decision situation. DeepPot does the same for Pot Fold.

For N players, every nonterminal public FOLD/STAY history is one strategic scenario:

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

The BTN all-prior-FOLD history is terminal and has no decision.

`src/deeppot/deepkk_style_export.py` now produces the canonical 494-scenario catalogue and one named STAY list per scenario for the mathematical DeepPot source.

---

# P3 — DeepKK-style unified base generator

Status: **IN PROGRESS**

Use the same decision methodology as DeepKK:

- [x] chance-sampled CFR+ engine;
- [x] linear average strategy;
- [x] exact state key instead of preflop 169 handclass;
- [x] deterministic seeds and manifests;
- [x] resumable per-flop production runner;
- [x] multiprocessing;
- [x] DeepKK-style EV evaluator implemented;
- [x] EV_FOLD and EV_STAY per exact infoset;
- [x] EV gap, standard error and CI95;
- [x] minimum effective-visit gate;
- [x] statistically confident best action when available;
- [x] inconclusive-state fallback to solver-average greedy action, exactly following the DeepKK principle;
- [x] 494-list mathematical TXT exporter;
- [ ] finish one unified Ryzen command/package that performs solve + EV audit + final merge + TXT/CSV/hash outputs for N=2..8.

Important: we copy the **method**, not blindly the numeric meaning of DeepKK's inner-loop counters. DeepKK's vectorized preflop `deals_per_iter` is not semantically equal to one DeepPot fixed-flop tree traversal. The official DeepPot finite compute budget will therefore be stated in native DeepPot units while retaining the same CFR+/linear-average/EV-CI/fallback procedure.

---

# P4 — Official Ryzen base run

Status: **NOT STARTED**

This is the DeepPot counterpart of the official DeepKK Ryzen run.

- [ ] freeze economy profile and generator/config SHA256;
- [ ] freeze one finite training/evaluation budget per N using the measured throughput;
- [ ] run N=2..8 on the Ryzen 9 with checkpoint/resume;
- [ ] solve every one of the 1,755 canonical flops for every supported N;
- [ ] run the DeepKK-style EV/CI audit;
- [ ] use confident EV-best action where supported;
- [ ] use solver-average greedy action where statistically inconclusive;
- [ ] record coverage/confidence summaries;
- [ ] preserve all mathematical source shards;
- [ ] merge final strategy and hash outputs.

There is **no requirement to pass the former universal `best-response <= 0.03 ante` gate**. Best-response results from P4C..P4I remain diagnostics, just as DeepKK quality was determined by its own production solve + EV/confidence methodology.

No new P4J/P4K method ladder is planned.

---

# P5 — Generate immutable `DeepPot.txt`

Status: **EXPORTER IMPLEMENTED / AWAITS OFFICIAL RUN**

The mathematical source deliberately mirrors DeepKK:

- `##notes##` provenance;
- explicit N/scenario catalogue;
- one named STAY list for each of the 494 strategic scenarios;
- absence from the STAY list means FOLD;
- exact state tokens `F####_H####` preserve flop-relative information;
- CSV source accompanies the TXT;
- all files are SHA256-hashed.

OpenPPL native handlists only encode preflop-style hole-card classes, so the mathematical `DeepPot.txt` uses exact state tokens. This does not change the DeepKK architecture: the immutable mathematical source remains separate from the operational OpenHoldem representation.

---

# P6 — Operational DeepPot / OpenHoldem

Status: **NOT STARTED**

Build the operational equivalent of DeepKK:

- [ ] dedicated Pot Fold tablemap/scraper;
- [ ] detect N=2..8;
- [ ] detect BTN/action order;
- [ ] reconstruct prior FOLD/STAY history;
- [ ] identify the exact one of 494 scenarios;
- [ ] read hero hole cards + flop;
- [ ] canonicalize to the same `flop_id + exact_hole_state_id` used by the mathematical source;
- [ ] compile the 494 mathematical STAY lists to an exact binary/DLL lookup;
- [ ] return only FOLD or POT/STAY;
- [ ] explicit HIT/MISS/state/action logs;
- [ ] fail closed on unknown/inconsistent state;
- [ ] preserve mathematical source separately from operational code.

The operational file should visually/structurally resemble DeepKK as far as OpenHoldem permits: scenario functions first, then base action routing, with no exploitation inside the base.

---

# P7 — Compiler/lookup validation

Status: **NOT STARTED**

- [ ] exhaustive round-trip of every exported final key;
- [ ] mathematical TXT/CSV action equals compiled runtime action;
- [ ] zero unknown keys for supported states;
- [ ] zero action mismatches;
- [ ] binary/runtime version and SHA recorded.

---

# P8 — Shadow live gate

Status: **NOT STARTED**

Attach DeepPot with autoplayer disabled and audit exactly **200 valid decisions**.

PASS requires correct N/scenario/cards/flop/state lookup and no illegal recommendation. One repeat is allowed only after a concrete runtime bug fix.

---

# P9 — Autoplayer live gate / Base v1

Status: **NOT STARTED**

At the smallest practical Pot Fold stake:

- [ ] exactly 200 valid live decisions;
- [ ] zero illegal/missed actions;
- [ ] logs match actual table state;
- [ ] observed payout/rake remains consistent with frozen economy;
- [ ] tag **DeepPot NLH Base v1**.

Profit/loss over 200 decisions is not a release criterion.

## ROADMAP COMPLETE

After P9, and only then, begin the DeepKK-style tracking/exploitation layer with fallback to frozen DeepPot Base v1.

---

# Archived research diagnostics

P4C, P4D, P4E, P4F, P4G, P4H and P4I remain in the repository for reproducibility. They explored stronger multiplayer exploitability/fixed-point criteria than were required for DeepKK. They are no longer the production route and will not be extended into an open-ended P4J/P4K sequence.
