# DeepPot NLH — Roadmap

Reference date: 2026-09-14

## Definition of done

DeepPot is done as a base bot when OpenHoldem can read the real Pot Fold state, map it losslessly to one of the exact trained infosets, execute a frozen production policy correctly, and that production policy has passed the finite base-policy robustness gate.

A population-exploit layer is optional and is a separate later project. It is not required for the base bot.

Authoritative current policy docs:

- `docs/DEEPPOT_DEEPKK_METHOD_LOCK.md`;
- `docs/BASE_POLICY_DECISION_20260914.md`;
- `docs/BASE_POLICY_ROBUSTNESS_GATE_20260914.md`;
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

Status: **ACTIVE — CURRENT NEXT GATE**

Current live baseline: **V2_SEL3500 greedy**.

Policy candidates:

1. mixed average CFR;
2. greedy majority action;
3. hybrid purification (60/70/80/90 majority thresholds).

What is already known:

- average CFR retains substantial real mixing; mixing cannot be dismissed as averaging residue;
- against mixed-CFR opponents, CFR majority frequency strongly aligns with EV-best as the majority moves away from 50%;
- 90–100% majority states matched the sampled EV-best action essentially perfectly;
- the near-50/50 region is the weak point for greedy;
- static BR-to-CFR is not an authorized production override.

### Next finite gate

Run:

```powershell
cd C:\DeepPot
git pull
powershell -ExecutionPolicy Bypass -File .\tools\analyze_policy_robustness_SEL3500.ps1
```

Frozen protocol: `docs/BASE_POLICY_ROBUSTNESS_GATE_20260914.md`.

It compares mixed, greedy and hybrid Hero policies against multiple fixed/non-adaptive opponent families: CFR mixed, CFR greedy, tighter, looser, sharpened, flattened and two position-dependent perturbations.

No training or production files are modified.

---

## D4 — Production-base release

Status: **WAITING FOR D3**

After the robustness gate:

- if greedy is robustly non-inferior, keep SEL3500 greedy;
- if a hybrid clearly improves robustness with negligible mean-EV cost, run one confirmation gate and then promote it;
- if mixed is materially safer across fixed populations, evaluate a mixed-runtime implementation;
- do not create more solver-depth tests unless the robustness result exposes a concrete convergence problem.

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

Run only the SEL3500 base-policy robustness audit. Do **not** run SEL4000 and do **not** apply the seven BR-to-CFR EV overrides.
