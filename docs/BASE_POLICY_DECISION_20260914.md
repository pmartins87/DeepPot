# DeepPot base-policy decision — CFR robustness vs static EV best response

Date: 2026-09-14

## Decision

For DeepPot, the production base must remain the CFR-derived equilibrium/self-play policy rather than a static best response to the CFR profile.

The DeepKK-style EV/CI machinery remains useful as a diagnostic tool, but it is no longer authorized to override the DeepPot production base merely because EV(FOLD) or EV(STAY) is higher against opponents fixed to the solver CFR policy.

This decision supersedes the DeepKK-parity release rule only for the final DeepPot base-policy selection. It does not invalidate prior CFR training, stability work, or EV diagnostics.

## Why

A static EV best response is conditional on an opponent model. In the current evaluator, the opponent model is the solver's own average mixed CFR policy. That is an internally coherent hypothetical profile, but it is not evidence that the actual KKPoker population follows that profile.

DeepKK could justify a best-response-oriented operational layer because later opponent-specific tracking could move the model away from the CFR prior as observations accumulated. DeepPot is intentionally not implementing that large opponent-model/exploitation layer at this stage. Therefore a permanent static best response to the solver profile would optimize against a fixed hypothetical population without an adaptation mechanism.

For unknown opponents, the CFR-derived self-play policy is the more robust base. In two-player zero-sum settings, an exact Nash strategy has the standard minimax/near-unexploitable interpretation. DeepPot N>2 does not inherit that full theorem: multiplayer CFR/self-play should be described as an approximate self-play equilibrium candidate, not as a formal guarantee of Nash or unexploitable play. Even so, it is a more defensible unknown-population base than a pure best response to one assumed profile.

## Critical distinction: mixed CFR vs greedy CFR

The true solver output is the average mixed CFR policy p(FOLD), p(STAY) at every exact infoset.

The current live snapshots are a deterministic projection:

- STAY if p(STAY) >= 0.5;
- otherwise FOLD.

That greedy bitset is not mathematically identical to the mixed CFR strategy and does not inherit all equilibrium properties of the mixed policy. This distinction must remain explicit in future work.

The DeepKK EV evaluator also did not assume that every villain used the greedy action. Its recursive expected-utility calculation integrated future actions using the full mixed policy probabilities. The final DeepKK export then made a deterministic decision: confident EV-best action when available, otherwise greedy average-CFR action.

## Current DeepPot status

- V2_SEL2500 performed very well in live play and remains a valid operational baseline.
- V2_SEL3000 is frozen as the latest research snapshot.
- Do not run SEL3500 merely to chase remaining Hamming movement.
- The seven high-sample EV mismatches found after SEL3000 are diagnostics, not authorized policy overrides. They show disagreement between deterministic greedy projection and a best response to the solver profile; they do not prove that the greedy action is inferior against the real population.
- The observed cashback is approximately 0.70% of Hero contribution. Rebate sensitivity did not materially change the mismatch set.

## New improvement path

1. Freeze SEL2500 and SEL3000. No further CFR continuation until a new gate is justified.
2. Keep the current deterministic SEL2500/SEL3000 runtime as operational baselines.
3. Measure the structure of the SEL3000 mixed policy: distribution of p(STAY), especially the mass near 0.5 and how it changes with training depth.
4. Build a separate mixed-policy runtime candidate that samples FOLD/STAY from the persisted average CFR probability instead of forcing argmax. Do not replace the live greedy runtime until this candidate is validated.
5. Compare three policies offline and, if practical, live in controlled blocks:
   - average mixed CFR;
   - deterministic greedy CFR projection;
   - static EV/BR-to-CFR diagnostic policy.
6. Evaluate robustness across more than one opponent model. The static EV/BR policy must not be promoted because it wins only against the CFR profile.
7. If a future population model is built from real Pot Fold data, exploitation may be layered on top of the frozen CFR base. Ambiguity or insufficient data must fall back to the CFR base.

## Release principle

For DeepPot without opponent-specific adaptation:

- preferred theoretical base: average mixed CFR/self-play policy;
- preferred deterministic fallback: greedy projection of average CFR;
- static best response to CFR: diagnostic only, not default production policy.

No source-locked mathematical file, CFR state, RNG trajectory, existing snapshot, DLL, or live formula is modified by this decision document.
