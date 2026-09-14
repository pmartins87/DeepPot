# DeepPot NLH — Roadmap

Reference date: 2026-09-14

## Definition of done

DeepPot is done as a base bot when OpenHoldem can read the real Pot Fold state, map it losslessly to one of the exact trained infosets, execute a frozen production policy correctly, and that production policy has passed the finite base-policy robustness gate.

A population-exploit layer is optional and is a separate later project. It is not required for the base bot.

Authoritative current policy docs:

- `docs/DEEPPOT_DEEPKK_METHOD_LOCK.md`;
- `docs/BASE_POLICY_DECISION_20260914.md`;
- `docs/BASE_POLICY_ROBUSTNESS_GATE_20260914.md`;
- `docs/BASE_POLICY_ROBUSTNESS_RESULT_20260914.md`;
- `docs/CONTINUOUS_TRAINING_V2.md`;
- `docs/CONTINUOUS_FAST_V2_GATE.md`.

---

## P0 — Mechanics/economy

Status: **MECHANICS PASS / ECONOMY PROVISIONAL**

- exact 2–8 player Pot Fold mechanics: PASS;
- one flop FOLD/STAY decision street: PASS;
- BTN last: PASS;
- automatic turn/river after decisions: PASS;
- gross rake model used by solver: provisional 2%, uncapped;
- live nominal rakeback: 50%;
- observed cashback in current live sample: approximately 0.70% of Hero contribution;
- official Pot Fold rake/cap publication: still unresolved.

Do not model the 50% nominal rakeback by simply changing gross rake from 2% to 1%.

---

## P1/P2 — Exact game/state space

Status: **PASS / CLOSED**

- 1,755 canonical flops;
- 1,286,792 exact canonical `(flop, hero hole)` states;
- 494 exact public decision scenarios across N2..N8;
- 635,675,248 exact infosets across the full game;
- no strategic card abstraction or pruning;
- global suit isomorphism only.

---

## P3–P7 — Base v1 / runtime / equivalence

Status: **PASS / FROZEN**

Base v1:

- 20k iterations/flop;
- 31 workers;
- elapsed 6.28 h;
- ~27.28 average training visits/exact infoset;
- immutable P5 freeze SHA256: `4d4077796ce81ec4d74a99818d69cc999221ad77c973c7d6fe7d4102d1a43a8a`.

Runtime/equivalence:

- all 635,675,248 infosets structurally resolvable;
- 0 unknown supported keys;
- 0 action-bit mismatches;
- 0 index metadata mismatches;
- functional `DeepPot.txt + user.dll + DeepPotRuntime` on i5;
- suit mapping and prior-action scraping bugs found live and corrected.

Base v1 remains archived and must never be overwritten.

---

## D1 — Resumable deep CFR infrastructure

Status: **PASS / CLOSED**

- exact CFR state persistence: regrets, strategy sums, visit counts, iteration count, RNG;
- atomic checkpoints;
- exact resume verified;
- FastChanceSampledCFRV2 exact-equivalence tests vs reference: PASS;
- 31 workers frozen as Ryzen winner;
- ~6.42M N8 CFR decision nodes/s in scaling benchmark;
- C++ kernel not justified at current runtime.

Canonical root:

`C:\DeepPot\runs\continuous_master_fast_v2`

---

## D2 — Deep training trajectory

Status: **SEL3500 COMPLETE / FURTHER DEPTH PAUSED**

Completed milestones on one continuous CFR trajectory:

- V2_1000: every exact infoset >=1000 visits;
- V2_1500;
- V2_2000;
- V2_SEL2500: selectively deepened 3,541 unstable `(N, flop)` tasks;
- V2_SEL3000: selectively deepened 1,756 tasks;
- V2_SEL3500: selectively deepened 329 tasks.

SEL3000 -> SEL3500:

- 1,386,540 action changes;
- 0.218121% global change;
- N2/N3/N4/N5: 0%;
- N6: 0.0139%;
- N7: 0.0768%;
- N8: 0.3827%;
- only 49/12,285 tasks remain >2% change;
- none remain >2.5%.

**Gate decision:** do not run SEL4000 now. Additional CFR depth is no longer the next bottleneck.

---

## D3 — Base-policy selection

Status: **PASS / CLOSED**

Selected production base: **V2_SEL3500 greedy**.

The frozen robustness gate compared mixed, greedy and hybrid60/70/80/90 against eight fixed/non-adaptive opponent families across 28 tasks with 1,500 common-random deals/task.

Greedy versus mixed:

- mean EV delta: **+0.10162 ante/hand**;
- worst population mean: **+0.09600**;
- worst N mean: **+0.02219**;
- cells > 0: **100%**;
- significant positive cells: **100%**;
- significant negative cells: **0%**;
- mean candidate regret: **0.00137**;
- max candidate regret: **0.01085**.

Greedy also beat every hybrid on mean EV and had the lowest mean/max candidate regret among purified candidates. No hybrid confirmation gate is justified.

Formal result:

`docs/BASE_POLICY_ROBUSTNESS_RESULT_20260914.md`

Static BR-to-CFR remains diagnostic only. The seven previously confirmed EV mismatches are not production overrides.

---

## D4 — Production-base release

Status: **ACTIVE — CURRENT NEXT GATE**

Policy selection is complete. The next finite step is operational release/freeze of **V2_SEL3500 greedy** using the existing deterministic runtime architecture.

Required release work:

1. identify/generate the exact SEL3500 greedy runtime artifacts from the canonical continuous state;
2. freeze their hashes and source snapshot/revision;
3. run the existing mathematical-to-runtime equivalence path on the release artifacts;
4. verify the OpenHoldem package on the i5 without changing the known-good tablemap/formula behavior;
5. freeze the production package only after those checks pass.

No mixed/hybrid runtime work is needed. Do not start SEL4000 merely because D3 is closed.

---

## E1 — Population exploitation (optional future track)

Status: **NOT STARTED / NOT YET JUSTIFIED**

Do not infer a population BR from OpenHoldem logs alone.

A real exploit layer requires a structured database with at least:

- N;
- actor/position;
- exact public scenario/history;
- board;
- observed FOLD/STAY;
- revealed showdown hole cards where available;
- sample confidence;
- principled treatment of hidden/censored folds.

Only open this track if real data shows stable, material population deviations large enough to justify the complexity. Any exploit layer must fail back to the frozen production base when evidence is weak.

---

## Immediate next action

Proceed with **D4 production-base release/freeze for V2_SEL3500 greedy**. Do **not** run SEL4000, do **not** build a mixed/hybrid runtime, and do **not** apply static BR-to-CFR EV overrides.
