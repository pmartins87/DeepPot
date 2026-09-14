# DeepPot base-policy robustness result — SEL3500

Date: 2026-09-14

Protocol: `docs/BASE_POLICY_ROBUSTNESS_GATE_20260914.md`

## Gate outcome

**PASS — retain V2_SEL3500 greedy as the production base.**

The predeclared robustness gate decisively favored the deterministic greedy projection over true mixed CFR and over every tested hybrid purification threshold.

This result does **not** claim that the synthetic opponent families equal the real KKPoker population. It establishes that, across the frozen finite stress test, the greedy projection was robust to a broad set of fixed/non-adaptive deviations from CFR and was the best of the tested base-policy candidates.

## Frozen protocol actually run

- 28 sampled canonical-flop tasks: 4 per N for N=2..8;
- 1,500 common-random chance deals per task;
- same chance deals reused across opponent families within each task;
- Hero candidates: mixed, greedy, hybrid60, hybrid70, hybrid80, hybrid90;
- opponent families: cfr_mixed, cfr_greedy, tight, loose, sharpened, flattened, early_tight_late_loose, early_loose_late_tight;
- gross rake: provisional 2%;
- Hero cashback in policy comparison: +0.70% of Hero contribution;
- read-only: no CFR state, RNG, snapshot, DLL, TXT or runtime bitset was modified.

## Policy summary

EV delta is in ante/hand relative to mixed CFR.

| policy | mean | worst population | worst N | cells > 0 | significant + | significant - | mean candidate regret | max candidate regret |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| mixed | +0.00000 | +0.00000 | +0.00000 | 0.0% | 0.0% | 0.0% | 0.10300 | 0.23959 |
| **greedy** | **+0.10162** | **+0.09600** | **+0.02219** | **100.0%** | **100.0%** | **0.0%** | **0.00137** | **0.01085** |
| hybrid60 | +0.09911 | +0.09364 | +0.02133 | 100.0% | 100.0% | 0.0% | 0.00389 | 0.01961 |
| hybrid70 | +0.09469 | +0.08979 | +0.02119 | 100.0% | 100.0% | 0.0% | 0.00831 | 0.03425 |
| hybrid80 | +0.08639 | +0.08227 | +0.02025 | 100.0% | 100.0% | 0.0% | 0.01661 | 0.06297 |
| hybrid90 | +0.06407 | +0.06121 | +0.01664 | 100.0% | 100.0% | 0.0% | 0.03893 | 0.11154 |

Greedy had the highest mean EV, the best worst-population mean, the best worst-N mean, and the lowest mean/max candidate regret of all non-mixed candidates. No hybrid improved the robustness/regret profile enough to justify its lower mean EV. Therefore the predeclared hybrid-confirmation condition was not triggered.

## By opponent population

| population | greedy | hybrid60 | hybrid70 | hybrid80 | hybrid90 |
|---|---:|---:|---:|---:|---:|
| cfr_mixed | +0.10183 | +0.09932 | +0.09501 | +0.08662 | +0.06425 |
| cfr_greedy | +0.10261 | +0.10009 | +0.09491 | +0.08683 | +0.06402 |
| tight | +0.09600 | +0.09364 | +0.08979 | +0.08227 | +0.06121 |
| loose | +0.10700 | +0.10435 | +0.09959 | +0.09029 | +0.06678 |
| sharpened | +0.10240 | +0.09982 | +0.09526 | +0.08687 | +0.06425 |
| flattened | +0.09955 | +0.09711 | +0.09300 | +0.08501 | +0.06354 |
| early_tight_late_loose | +0.10351 | +0.10077 | +0.09645 | +0.08787 | +0.06505 |
| early_loose_late_tight | +0.10009 | +0.09780 | +0.09351 | +0.08532 | +0.06345 |

Greedy was positive in every population aggregate and its weakest tested population, `tight`, was still +0.09600 ante/hand versus mixed.

## By N

| N | greedy | hybrid60 | hybrid70 | hybrid80 | hybrid90 |
|---|---:|---:|---:|---:|---:|
| 2 | +0.02219 | +0.02133 | +0.02119 | +0.02025 | +0.01664 |
| 3 | +0.04134 | +0.04075 | +0.03929 | +0.03839 | +0.03251 |
| 4 | +0.06646 | +0.06142 | +0.06025 | +0.05623 | +0.04676 |
| 5 | +0.08557 | +0.08470 | +0.08213 | +0.07892 | +0.06368 |
| 6 | +0.13602 | +0.13510 | +0.12682 | +0.11434 | +0.08029 |
| 7 | +0.15753 | +0.15639 | +0.15157 | +0.13461 | +0.09544 |
| 8 | +0.20225 | +0.19409 | +0.18158 | +0.16196 | +0.11316 |

Greedy was positive for every N. The practical advantage over mixed increased strongly with table size in this stress test.

## Decision against predeclared rule

The gate rule said to retain greedy if it had positive overall mean and no materially negative population/N aggregate. Greedy exceeded that requirement by a wide margin:

- overall mean: +0.10162 ante/hand;
- worst population mean: +0.09600;
- worst N mean: +0.02219;
- positive cells: 100%;
- statistically significant positive cells: 100%;
- statistically significant negative cells: 0%.

The gate also allowed a hybrid to advance only if it materially improved worst-case or candidate-regret behavior without comparable EV loss. No hybrid did so; greedy itself had the lowest mean regret (0.00137) and lowest max regret (0.01085) among the purified candidates.

Therefore no second hybrid confirmation gate is justified.

## Production consequence

- Production base: **V2_SEL3500 greedy**.
- Mixed CFR remains the theoretical/reference policy, not the production policy.
- Hybrid policies are rejected for the current base release.
- The seven BR-to-CFR EV mismatches remain diagnostic only; no static EV overrides are authorized.
- SEL4000 remains paused; this robustness result does not expose a convergence problem that would justify more depth.
- The existing deterministic runtime architecture is appropriate for the selected base policy; a mixed/hybrid runtime is not needed.

## Scope limitation

These opponent families are synthetic fixed stress tests. The result does not prove that greedy is an equilibrium strategy or that it is globally optimal against the actual KKPoker population. A future population-exploit layer would require real structured population data and is a separate optional track.
