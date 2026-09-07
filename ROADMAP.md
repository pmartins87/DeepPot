# DeepPot Roadmap

## Project priority

Build the **mathematical base strategy first**, following the DeepKK pattern. Opponent tracking and exploitation remain deliberately deferred until the base solver, validation, policy format and runtime are solid.

## P0 — Rules and economy gate

Status: **IN PROGRESS, no longer blocking engineering**

- [x] Confirm official core rules: no blinds, all players ante, preflop skipped, action begins on flop, fixed pot-sized continue action or fold, automatic turn/river after flop action.
- [x] Confirm NLH and PLO availability from official KKPoker source.
- [x] Confirm table capacity: up to 8 seats.
- [x] Confirm BTN is last to act in live Pot Fold.
- [x] Confirm last-player/no-op terminal semantics when every previous player folds.
- [x] Confirm uncontested pots are still raked.
- [ ] Confirm exact Pot Fold rake % by variant/stake/player count/pot geometry.
- [ ] Confirm exact Pot Fold rake cap and the unit used for the cap on ante-only tables.
- [ ] Explain the live payout observations 84 -> 81.12 and 45 -> 43.38.
- [ ] Confirm exact ante values/ranges shown in the KKPoker lobby.
- [ ] Confirm insufficient-stack/side-pot behavior, if relevant.
- [ ] Freeze rakeback/PVI treatment for the official strategy economy.

**Gate P0:** engineering and pilot solving may proceed with parameterized economics. Do not label any strategy as the official economic solution until rake/cap/reward semantics are frozen.

## P1 — NLH game kernel

Status: **CORE COMPLETE**

- [x] Card/deck model.
- [x] Pot Fold action tree for 2–8 players.
- [x] Fixed continue cost = initial pot.
- [x] BTN-last neutral action ordering.
- [x] Terminal showdown/runout logic.
- [x] Uncontested-pot terminal logic, including zero-STAY BTN win.
- [x] Nominal rake + cap model.
- [x] Per-player terminal utilities and tie splitting.
- [ ] Separate rakeback/PVI reward model.
- [x] Unit tests for core terminal geometries.

## P2 — State canonicalization and equity engine

Status: **PROTOTYPE COMPLETE / OPTIMIZATION PENDING**

- [x] Canonicalize flop + hole cards under all 24 suit permutations.
- [x] Enumerate and regression-test the 1,755 standard NLH flop isomorphism classes.
- [x] Exact 5-card and 7-card evaluator.
- [x] Exact cached-ready HU turn-river enumeration API (990 runouts for two known hands on a flop).
- [x] Multiway showdown evaluator for known hands/runout.
- [ ] Fast evaluator implementation suitable for production-scale solving.
- [ ] Monte Carlo/equity fallback with deterministic seeds and confidence intervals.
- [ ] Cache format with version/hash metadata.
- [ ] Differential validation against an independent evaluator/library.

## P3 — DeepPot base solver

Status: **CHANCE-SAMPLED CFR PROTOTYPE IMPLEMENTED**

The key structural difference from DeepKK is the state space: Pot Fold is **flop-conditioned**, not a 169 preflop-hand-class game.

- [x] Fixed-flop subgame solver architecture.
- [x] Binary actions: STAY/POT and FOLD.
- [x] Modes parameterized for 2–8 players.
- [x] Stable scenario/history naming with neutral A0/A1/.../BTN actors.
- [x] Chance-sampled private cards + turn/river.
- [x] Full binary action-tree traversal per sampled deal.
- [x] CFR+ regret floor and linear strategy averaging prototype.
- [x] Information-set keys expose only player count, actor/history, flop and actor hole cards.
- [x] Deterministic-seed smoke tests, including 8-player execution.
- [ ] Add production run configuration/manifest analogous to DeepKK.
- [ ] Add multiprocessing by canonical flop.
- [ ] Add checkpoint/resume.
- [ ] Export immutable base policy + EV reference.
- [ ] Evaluate exact-state storage versus strategically safe abstraction.
- [ ] Boundary refinement for near-indifferent states.
- [ ] Decide whether production base solver remains CFR-family after validation of rake/multiplayer game-theory caveats.

## P4 — Solver validation

Status: **NEXT CRITICAL GATE**

- [ ] Cross-seed policy stability.
- [ ] Mean/max positive regret.
- [ ] Best-response exploitability estimate for HU.
- [ ] Multiplayer response/robustness metrics for N>2.
- [ ] EV confidence intervals.
- [ ] Coverage/min-visits report per canonical state.
- [ ] Exact-vs-sampled equity regression tests.
- [ ] Reproducible run manifest and SHA256 hashes.
- [ ] Validate that path-dependent rake does not invalidate the chosen convergence target.

## P5 — Operational base-policy format

- [ ] Define policy key: variant | players | scenario | canonical_flop | canonical_hole_state.
- [ ] Compact lookup format suitable for OpenHoldem DLL runtime.
- [ ] Preserve mathematical policy separately from operational policy.
- [ ] Safe unknown-state fallback.
- [ ] Version policy by complete economic configuration.

## P6 — OpenHoldem base runtime

This is intentionally brought before exploitation. The first live DeepPot must be able to play **base strategy only**.

- [ ] Pot Fold tablemap/scraper validation.
- [ ] Dynamic 2–8 player action-order mapping with BTN last.
- [ ] Formula scenario detection.
- [ ] DLL/base-policy lookup.
- [ ] Single decision symbol.
- [ ] HIT/MISS/mismatch logs.
- [ ] Fail closed on unknown state.
- [ ] Dedicated runtime profile separate from AoF and Crusher.
- [ ] Shadow mode before autoplayer.

## P7 — Base live validation

- [ ] Compare detected state with reviewed hands/screenshots/logs.
- [ ] Verify actual rake/fee deductions against model.
- [ ] Small-stakes controlled base-only test.
- [ ] Validate recommendation/action agreement.
- [ ] Publish DeepPot NLH Base v1 only after mechanics/economy match reality.

---

# Exploitation phase — intentionally after Base v1

## P8 — Pot Fold tracker / frame reconstructor

Reuse the proven DeepKK structure, but reconstruct flop decisions instead of preflop all-in/fold.

- [ ] Frame schema.
- [ ] Hand audit table.
- [ ] Reconstructed actions table.
- [ ] Action-level eligibility flags.
- [ ] Pot/stack/card-state transition rules.
- [ ] Hero-context separation.
- [ ] Validation SQL.

## P9 — Opponent identity and statistics

- [ ] PlayerAliases.
- [ ] AutoAliasCandidates.
- [ ] Alias flattening.
- [ ] OpponentStats by variant/player-count/scenario/flop abstraction.
- [ ] PoolStats priors.
- [ ] Shrinkage/confidence model.

## P10 — Exploit: HU and VS1

- [ ] Exact/fixed-opponent best-response profiles.
- [ ] Sample thresholds and shrinkage.
- [ ] MESPolicy-equivalent table for Pot Fold.
- [ ] Fallback to DeepPot base on weak evidence.

## P11 — Multiway exploit

- [ ] Full observed vector by relevant opponents.
- [ ] Cartesian catalog only for actually observed vectors.
- [ ] Train missing vectors.
- [ ] Runtime enable gate only after catalog coverage is complete for the published snapshot.

## P12 — PLO extensions

- [ ] PLO4 Pot Fold.
- [ ] PLO5 Pot Fold.
- [ ] Omaha exact-card-use evaluator.
- [ ] New state abstraction/canonicalization.
- [ ] Separate strategies and validation artifacts.
