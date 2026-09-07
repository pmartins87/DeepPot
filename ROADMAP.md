# DeepPot Roadmap

## P0 — Rules and economy gate

Status: **IN PROGRESS**

- [x] Confirm official core rules: no blinds, all players ante, preflop skipped, action begins on flop, fixed pot-sized continue action or fold, automatic turn/river after flop action.
- [x] Confirm NLH and PLO availability from official KKPoker source.
- [ ] Confirm exact Pot Fold rake % by variant/stake.
- [ ] Confirm exact Pot Fold rake cap and the unit used for the cap on ante-only tables.
- [ ] Confirm whether KKPoker's general `<=3 players => half designated rake` rule applies to Pot Fold.
- [ ] Confirm all available table sizes/player counts.
- [ ] Confirm exact ante values/ranges shown in the KKPoker lobby.
- [ ] Confirm last-player/no-op terminal semantics when every previous player folds.
- [ ] Confirm insufficient-stack/side-pot behavior, if possible.
- [ ] Capture a small set of live screenshots/logs for table-state semantics and OpenHoldem mapping.

**Gate P0:** do not publish an official DeepPot strategy until rake/cap and action semantics are frozen.

## P1 — NLH game kernel

- [ ] Card/deck model.
- [ ] Pot Fold action tree for N players.
- [ ] Fixed continue cost = initial pot.
- [ ] Terminal showdown/runout logic.
- [ ] Uncontested-pot terminal logic.
- [ ] Nominal rake + cap model.
- [ ] Separate rakeback/PVI reward model (do not bury it inside pot rake).
- [ ] Unit tests for all terminal geometries.

## P2 — State canonicalization and equity engine

- [ ] Canonicalize flop + hole cards under suit permutations.
- [ ] Enumerate the 1,755 standard NLH flop isomorphism classes.
- [ ] Exact 5/7-card evaluator.
- [ ] Exact or cached turn-river runouts for HU.
- [ ] Multiway showdown evaluator.
- [ ] Monte Carlo fallback with deterministic seeds and confidence intervals.
- [ ] Cache format with version/hash metadata.

## P3 — DeepPot base solver

The key structural difference from DeepKK is the state space: Pot Fold is **flop-conditioned**, not a 169 preflop-hand-class game.

- [ ] Solve independently by canonical flop class.
- [ ] Binary actions: STAY/POT and FOLD.
- [ ] Modes parameterized by player count.
- [ ] Scenario/history naming analogous to DeepKK, but with prior STAY/FOLD actions.
- [ ] CFR+/MCCFR prototype with linear averaging.
- [ ] Evaluate exact-state storage versus strategically safe abstraction.
- [ ] Boundary refinement for near-indifferent states.
- [ ] Export immutable base policy + EV reference.

## P4 — Solver validation

- [ ] Cross-seed policy stability.
- [ ] Mean/max positive regret.
- [ ] Best-response exploitability estimate.
- [ ] EV confidence intervals.
- [ ] Coverage/min-visits report per canonical state.
- [ ] Exact-vs-sampled equity regression tests.
- [ ] Reproducible run manifest and SHA256 hashes.

## P5 — Operational policy format

- [ ] Define policy key: variant | players | scenario | canonical_flop | canonical_hole_state.
- [ ] Compact lookup format suitable for OpenHoldem DLL runtime.
- [ ] Preserve mathematical policy separately from operational policy.
- [ ] Safe unknown-state fallback.

## P6 — Pot Fold tracker / frame reconstructor

Reuse the proven DeepKK structure, but reconstruct flop decisions instead of preflop all-in/fold.

- [ ] Frame schema.
- [ ] Hand audit table.
- [ ] Reconstructed actions table.
- [ ] Action-level eligibility flags.
- [ ] Pot/stack/card-state transition rules.
- [ ] Hero-context separation.
- [ ] Validation SQL.

## P7 — Opponent identity and statistics

- [ ] PlayerAliases.
- [ ] AutoAliasCandidates.
- [ ] Alias flattening.
- [ ] OpponentStats by variant/player-count/scenario/flop abstraction.
- [ ] PoolStats priors.
- [ ] Shrinkage/confidence model.

## P8 — Exploit: HU and VS1

- [ ] Exact/fixed-opponent best-response profiles.
- [ ] Sample thresholds and shrinkage.
- [ ] MESPolicy-equivalent table for Pot Fold.
- [ ] Fallback to DeepPot base on weak evidence.

## P9 — Multiway exploit

- [ ] Full observed vector by relevant opponents.
- [ ] Cartesian catalog only for actually observed vectors.
- [ ] Train missing vectors.
- [ ] Runtime enable gate only after catalog coverage is complete for the published snapshot.

## P10 — OpenHoldem runtime

- [ ] Pot Fold tablemap/scraper validation.
- [ ] Formula scenario detection.
- [ ] DLL lookup.
- [ ] Single decision symbol.
- [ ] HIT/MISS/mismatch logs.
- [ ] Fail closed to base policy.
- [ ] Dedicated runtime profile separate from AoF and Crusher.

## P11 — Live validation

- [ ] Shadow mode first: log recommendations without acting.
- [ ] Compare detected state with hand review/screenshots.
- [ ] Small-stakes controlled test.
- [ ] Verify actual rake and rakeback credits against model.
- [ ] Pool-stat collection.
- [ ] Publish DeepPot NLH v1 only after mechanics/economy match reality.

## P12 — PLO extensions

- [ ] PLO4 Pot Fold.
- [ ] PLO5 Pot Fold.
- [ ] Omaha exact-card-use evaluator.
- [ ] New state abstraction/canonicalization.
- [ ] Separate strategies and validation artifacts.
