# DeepPot base-policy decision — CFR robustness vs static EV best response

Date: 2026-09-14

## Current decision

The production base must remain **CFR-derived**. A static best response to the solver's own CFR profile is diagnostic only and is not authorized to overwrite the production base.

The current live baseline is now **V2_SEL3500 greedy** because SEL3500 is a continuation of the same exact CFR trajectory, differs from SEL3000 in only 0.218121% of all actions, and further reduced the remaining instability without changing the game model.

Do not run SEL4000 at this stage. The next gate is policy-selection robustness, not additional CFR depth.

## Why static EV/BR-to-CFR is not the production answer

A best response is conditional on an opponent model. The DeepKK-style evaluator integrates opponents using the full mixed CFR policy and chooses the Hero action with the highest conditional EV when statistically confident. That is coherent against CFR opponents, but it is not evidence that the real KKPoker population follows that profile.

DeepKK could later move away from the CFR prior because it had an opponent/player database and exploitation layer. DeepPot intentionally does not yet have an equivalent population database. Therefore a permanent BR to a fixed CFR opponent profile would optimize against a hypothetical population with no adaptation mechanism.

EV/CI remains valuable for diagnostics and targeted investigations. It is not an automatic production override.

## Mixed CFR vs greedy CFR

The true average CFR output is a mixed policy `p(FOLD), p(STAY)` at each exact infoset.

The live runtime uses a deterministic projection:

- STAY if `p(STAY) >= 0.5`;
- otherwise FOLD.

This greedy projection is not identical to the mixed CFR policy and does not inherit every equilibrium property of the mix.

However, recent SEL3500 measurements materially strengthen the practical case for greedy outside the near-50/50 region.

### Mixing-structure audit

Across all 635,675,248 exact infosets:

- average CFR near-pure (<=1% or >=99%): 8.030%;
- average CFR mixed 10–90: 40.917%;
- average CFR 45–55: 2.723%;
- current regret-matching mixed 10–90: 32.237%;
- average-greedy vs current-greedy side disagreement: 4.823%.

The mixed mass is not merely historical averaging residue: among average-CFR 10–90 states, 77.49% are still mixed in current regret matching. Therefore mixed CFR cannot be dismissed wholesale as stale noise.

### Frequency-vs-EV alignment audit

Against opponents fixed to SEL3500 mixed CFR, the CFR majority action matched the point-estimate EV-best pure action increasingly often as majority frequency moved away from 50%:

- 50–55%: 40.0%;
- 55–60%: 56.7%;
- 60–70%: 68.3%;
- 70–80%: 77.4%;
- 80–90%: 96.7%;
- 90–95%: 100%;
- 95–99%: 100%;
- 99–100%: 100%.

Among statistically confident states overall, the majority action matched EV-best 97.12%. Greedy also beat mixed by +0.06636 ante/hand on average in that sampled CFR-opponent environment.

This strongly supports the user's practical hypothesis that majority frequency is often a useful proxy for action quality, especially once the majority is strong. It still does **not** prove that the majority action is best against the actual KKPoker population.

## SEL3500 convergence status

SEL3000 -> SEL3500 changed only 1,386,540 of 635,675,248 actions = **0.218121%**.

By N:

- N2: 0.0000%;
- N3: 0.0000%;
- N4: 0.0000%;
- N5: 0.0000%;
- N6: 0.0139%;
- N7: 0.0768%;
- N8: 0.3827%.

Only 49/12,285 tasks remained above 2% action change; none remained above 2.5%. This is sufficient to freeze additional CFR depth for now.

## Rakeback/economy note

The solver track still uses provisional gross rake = 2%, uncapped. The live data showed approximately **0.70% cashback on Hero contribution** from the user's nominal 50% rakeback. Conditional sensitivity tests found that this observed cashback changed only a small fraction of marginal action comparisons and did not explain the main greedy-vs-EV disagreements.

Do not simplify the economics by replacing 2% gross rake with 1% rake. Rake is removed from the pot first; cashback is player-specific and contribution/PVI-dependent.

## Current improvement path

1. **Live baseline:** V2_SEL3500 greedy.
2. **No SEL4000 now.**
3. **No automatic EV overrides.**
4. Resolve `mixed vs greedy vs hybrid` with the finite robustness gate in `docs/BASE_POLICY_ROBUSTNESS_GATE_20260914.md`.
5. The gate compares Hero mixed, greedy and hybrid purification policies against multiple fixed/non-adaptive opponent families derived from SEL3500, not just CFR opponents.
6. Only after the base policy is resolved decide whether a population-exploitation project is worth its complexity.

## Population exploitation

OpenHoldem logs alone are not enough to build a high-quality population best response because folded hole cards are censored and the logs do not provide a complete conditional range database.

A real exploit layer would require a structured database of public scenario, N, actor/position, board, action, showdown/revealed hole cards and sample confidence, with a principled treatment of hidden folds. If such a database later demonstrates stable, material deviations, exploitation may be layered conservatively on top of the frozen base with fallback to base.

Until then, do not create a global exploitation layer merely because it is technically possible.

## Release principle

- mixed CFR: theoretical robustness reference;
- greedy CFR: current practical/live baseline;
- hybrid CFR: candidate if robustness testing shows a better trade-off;
- static BR to CFR: diagnostic only;
- population BR: future exploit layer only if real conditional population data supports it.

No source-locked mathematical file, CFR state, RNG trajectory, existing snapshot, DLL or live formula is modified by this decision document.
