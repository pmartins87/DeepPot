# DeepPot base-policy decision — CFR robustness vs static EV best response

Date: 2026-09-14

## Final base-policy decision

**Production base: V2_SEL3500 greedy.**

The finite predeclared robustness gate is complete and decisively supports keeping the deterministic majority-action projection of SEL3500 average CFR.

Formal result: `docs/BASE_POLICY_ROBUSTNESS_RESULT_20260914.md`.

No hybrid confirmation gate is needed. Mixed CFR remains a reference policy, not the production policy. Static BR-to-CFR remains diagnostic only and is not authorized to overwrite production decisions.

Do not run SEL4000 at this stage.

## Robustness gate result

The frozen gate compared:

- mixed CFR;
- greedy CFR;
- hybrid60;
- hybrid70;
- hybrid80;
- hybrid90;

against eight fixed/non-adaptive opponent families derived from SEL3500:

- cfr_mixed;
- cfr_greedy;
- tight;
- loose;
- sharpened;
- flattened;
- early_tight_late_loose;
- early_loose_late_tight.

Protocol: 28 canonical-flop tasks, 1,500 common-random chance deals per task, provisional gross rake 2% and +0.70% Hero cashback on contribution.

Greedy result versus mixed CFR:

- mean EV delta: **+0.10162 ante/hand**;
- worst population mean: **+0.09600**;
- worst N mean: **+0.02219**;
- cells > 0: **100%**;
- statistically significant positive cells: **100%**;
- statistically significant negative cells: **0%**;
- mean candidate regret: **0.00137**;
- max candidate regret: **0.01085**.

Greedy also had the highest mean EV and the lowest mean/max candidate regret among the non-mixed candidates. No hybrid improved worst-case behavior or candidate regret enough to justify its lower mean EV.

This satisfies the predeclared greedy-retention rule by a wide margin.

## Why static EV/BR-to-CFR is not the production answer

A best response is conditional on an opponent model. The DeepKK-style evaluator integrates opponents using the full mixed CFR policy and chooses the Hero action with the highest conditional EV when statistically confident. That is coherent against CFR opponents, but it is not evidence that the real KKPoker population follows that profile.

DeepKK could later move away from the CFR prior because it had an opponent/player database and exploitation layer. DeepPot intentionally does not yet have an equivalent population database. Therefore a permanent BR to a fixed CFR opponent profile would optimize against a hypothetical population with no adaptation mechanism.

EV/CI remains valuable for diagnostics and targeted investigations. It is not an automatic production override.

The seven high-sample greedy-vs-BR-to-CFR mismatches remain diagnostic only.

## Mixed CFR vs greedy CFR

The true average CFR output is a mixed policy `p(FOLD), p(STAY)` at each exact infoset.

The production runtime uses a deterministic projection:

- STAY if `p(STAY) >= 0.5`;
- otherwise FOLD.

This greedy projection is not identical to the mixed CFR policy and does not inherit every equilibrium property of the mix.

However, two independent measurements now support it as the practical production base:

1. the frequency-vs-EV audit showed strong alignment between the CFR majority action and EV-best action as the majority frequency moved away from 50%;
2. the frozen robustness gate showed greedy outperforming mixed across every sampled fixed population family and every N aggregate.

The second result is materially stronger for the production decision because it did not rely on a single CFR-opponent family.

## Mixing-structure audit

Across all 635,675,248 exact infosets:

- average CFR near-pure (<=1% or >=99%): 8.030%;
- average CFR mixed 10–90: 40.917%;
- average CFR 45–55: 2.723%;
- current regret-matching mixed 10–90: 32.237%;
- average-greedy vs current-greedy side disagreement: 4.823%.

The mixed mass is not merely historical averaging residue: among average-CFR 10–90 states, 77.49% are still mixed in current regret matching. Therefore mixed CFR cannot be dismissed as stale noise. The production decision is instead based on measured robustness of the greedy projection.

## Frequency-vs-EV alignment audit

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

This audit was supportive but not sufficient alone; the later robustness gate closed the practical base-policy question.

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

Only 49/12,285 tasks remained above 2% action change; none remained above 2.5%. The robustness gate did not reveal a concrete convergence failure. Additional CFR depth is therefore not justified now.

## Rakeback/economy note

The solver track still uses provisional gross rake = 2%, uncapped. The live data showed approximately **0.70% cashback on Hero contribution** from the user's nominal 50% rakeback.

Do not simplify the economics by replacing 2% gross rake with 1% rake. Rake is removed from the pot first; cashback is player-specific and contribution/PVI-dependent.

The robustness gate included the observed +0.70% Hero cashback on contribution in policy comparisons.

## Production release consequence

1. **Production base:** V2_SEL3500 greedy.
2. **No SEL4000 now.**
3. **No automatic EV overrides.**
4. **No hybrid or mixed runtime implementation is needed for the current base release.**
5. Existing deterministic runtime architecture is compatible with the selected policy.
6. The next work should be operational release/freeze and live validation of SEL3500 greedy, not another base-policy sweep.
7. Population exploitation remains a separate optional future track.

## Population exploitation

OpenHoldem logs alone are not enough to build a high-quality population best response because folded hole cards are censored and the logs do not provide a complete conditional range database.

A real exploit layer would require a structured database of public scenario, N, actor/position, board, action, showdown/revealed hole cards and sample confidence, with a principled treatment of hidden folds. If such a database later demonstrates stable, material deviations, exploitation may be layered conservatively on top of the frozen base with fallback to base.

Until then, do not create a global exploitation layer merely because it is technically possible.

## Release principle

- mixed CFR: theoretical/reference policy;
- **greedy CFR: selected production base**;
- hybrid CFR: rejected for the current base release by the frozen robustness gate;
- static BR to CFR: diagnostic only;
- population BR: future exploit layer only if real conditional population data supports it.

No source-locked mathematical file, CFR state, RNG trajectory, existing snapshot, DLL or live formula is modified by this decision document.
