# DeepPot base-policy decision — CFR robustness vs static EV best response

Date: 2026-09-14

## Decision

For DeepPot, the production base must remain CFR-derived rather than a static best response to the CFR profile.

The DeepKK-style EV/CI machinery remains useful as a diagnostic tool, but it is no longer authorized to override the DeepPot production base merely because EV(FOLD) or EV(STAY) is higher against opponents fixed to the solver CFR policy.

This decision supersedes the DeepKK-parity release rule only for the final DeepPot base-policy selection. It does not invalidate prior CFR training, stability work, or EV diagnostics.

## Why

A static EV best response is conditional on an opponent model. In the current evaluator, the opponent model is the solver's own average mixed CFR policy. That is an internally coherent hypothetical profile, but it is not evidence that the actual KKPoker population follows that profile.

DeepKK could justify a best-response-oriented operational layer because later opponent-specific tracking could move the model away from the CFR prior as observations accumulated. DeepPot is intentionally not implementing that large opponent-model/exploitation layer at this stage. Therefore a permanent static best response to the solver profile would optimize against a fixed hypothetical population without an adaptation mechanism.

For unknown opponents, the CFR-derived self-play policy is the more robust base. In two-player zero-sum settings, an exact Nash strategy has the standard minimax/near-unexploitable interpretation. DeepPot N>2 does not inherit that full theorem: multiplayer CFR/self-play should be described as an approximate self-play equilibrium candidate, not as a formal guarantee of Nash or unexploitable play.

## Critical distinction: mixed CFR vs greedy CFR

The true solver output is the average mixed CFR policy p(FOLD), p(STAY) at every exact infoset.

The current live snapshots are a deterministic projection:

- STAY if p(STAY) >= 0.5;
- otherwise FOLD.

That greedy bitset is not mathematically identical to the mixed CFR strategy and does not inherit all equilibrium properties of the mixed policy.

Crucially, p(STAY) > 0.5 is not a confidence score that STAY has higher EV against an arbitrary real population. In an exact equilibrium, actions that remain in the support can be approximately indifferent against the equilibrium opponent profile even if their mixing frequencies are not 50/50. Therefore "choose the most probable CFR action" is a deterministic heuristic/projection, not a theorem that the selected action is universally best.

If real opponents never adapt to Hero, the anti-exploitation value of exact mixing is less operationally important than against adaptive opponents. However that fact alone still does not prove greedy is superior: the best deterministic action would be the best response to the actual fixed population, which is currently unknown. Without such a population model, mixed CFR provides more game-theoretic robustness; greedy CFR may still be an excellent practical approximation and currently has strong live evidence.

The DeepKK EV evaluator also did not assume that every villain used the greedy action. Its recursive expected-utility calculation integrated future actions using the full mixed policy probabilities. The final DeepKK export then made a deterministic decision: confident EV-best action when available, otherwise greedy average-CFR action.

## Current DeepPot status

- V2_SEL2500 performed very well in live play and remains a valid historical operational baseline.
- V2_SEL3000 is the preferred current live/research baseline unless live evidence shows a regression.
- The seven high-sample EV mismatches found after SEL3000 are diagnostics, not authorized policy overrides. They show disagreement between deterministic greedy projection and a best response to the solver profile; they do not prove that the greedy action is inferior against the real population.
- The observed cashback is approximately 0.70% of Hero contribution. Rebate sensitivity did not materially change the mismatch set.
- SEL3500 was started before this clarification. It may finish as a convergence/stability experiment because it only continues the 329 least-stable independent (N, flop) CFR tasks on their existing trajectory. Completion does not automatically promote SEL3500 to live production and is no longer justified as a way to force agreement with EV/BR-to-CFR.

## New improvement path

1. Keep V2_SEL3000 as the current live baseline.
2. Allow the already-started SEL3500 continuation to finish, but treat it strictly as a research convergence snapshot until compared with SEL3000.
3. Do not apply EV/BR-to-CFR overrides to production.
4. Measure the structure of the average mixed CFR policy: distribution of p(STAY), especially mass near 0.5 and how it changes from SEL3000 to SEL3500.
5. Compare mixed CFR and greedy CFR offline under multiple opponent families rather than one CFR opponent model. Include at minimum: mixed-CFR opponents, greedy-CFR opponents, systematically tighter populations, systematically looser populations, and perturbations by public scenario/position.
6. Evaluate both average EV and downside/robustness across those opponent families. Greedy should only replace mixed as a theoretically preferred base if it demonstrates a robust advantage, not merely because p(action) is larger.
7. If real population data later becomes rich enough to estimate conditional ranges/actions, exploitation can be layered on top of the CFR base. Ambiguity or insufficient data must fall back to the frozen CFR-derived base.

## Release principle

For DeepPot without opponent-specific adaptation:

- mixed CFR: theoretical robustness reference;
- greedy CFR: current practical/live baseline and deterministic projection;
- static best response to CFR: diagnostic only;
- population best response: future exploit layer only if supported by real conditional population data.

No source-locked mathematical file, CFR state, RNG trajectory, existing snapshot, DLL, or live formula is modified by this decision document.
