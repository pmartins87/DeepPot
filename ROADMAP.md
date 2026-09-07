# DeepPot Roadmap

## Project priority

Build the **mathematical base strategy first**, following the DeepKK pattern. Opponent tracking and exploitation remain deliberately deferred until the base solver, validation, policy format and runtime are solid.

Second principle: **exact-state first**. DeepPot will preserve every strategically distinct flop+hole state and collapse only true suit isomorphisms. Lossy equity/potential/card bucketing is a fallback only if the optimized exact path later fails a measured computational-feasibility gate.

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

## P2 — Exact state canonicalization and equity engine

Status: **EXACT REPRESENTATION PROVEN / PERFORMANCE OPTIMIZATION PENDING**

- [x] Canonicalize flop + hole cards under all 24 suit permutations.
- [x] Enumerate and regression-test the 1,755 standard NLH flop isomorphism classes.
- [x] Prove exact flop+hole state count with Burnside's lemma: **1,286,792** states modulo only global suit relabeling.
- [x] Document why `1,755 x 169` is not exact after the flop is visible.
- [x] Regression-test exact state-space and public-scenario counts.
- [x] Exact 5-card and 7-card evaluator.
- [x] Exact cached-ready HU turn-river enumeration API (990 runouts for two known hands on a flop).
- [x] Multiway showdown evaluator for known hands/runout.
- [ ] Fast evaluator implementation suitable for production-scale solving.
- [ ] Dense integer ID for every exact canonical flop+hole state.
- [ ] Per-flop exact-state index tables.
- [ ] Cache format with version/hash metadata.
- [ ] Differential validation against an independent evaluator/library.

## P3 — DeepPot exact base solver

Status: **CHANCE-SAMPLED CFR PROTOTYPE IMPLEMENTED; OPTIMIZATION NEXT**

The production target is not a 169-class-per-flop approximation. It is:

`exact canonical flop+hole state | exact player count | exact public FOLD/STAY history -> policy`

Suit relabeling is exact symmetry, not strategic abstraction.

- [x] Fixed-flop subgame solver architecture.
- [x] Binary actions: STAY/POT and FOLD.
- [x] Modes parameterized for 2–8 players.
- [x] Stable scenario/history naming with neutral A0/A1/.../BTN actors.
- [x] Chance-sampled private cards + turn/river.
- [x] Full binary action-tree traversal per sampled deal.
- [x] CFR+ regret floor and linear strategy averaging prototype.
- [x] Information-set keys expose only player count, actor/history, flop and actor hole cards.
- [x] Deterministic-seed smoke tests, including 8-player execution.
- [ ] Replace string-key dictionary hot path with dense integer-indexed node storage where possible.
- [ ] Replace/accelerate terminal evaluator hot path.
- [ ] Add batched/vectorized deal generation and updates analogous to DeepKK where mathematically valid.
- [ ] Add production run configuration/manifest analogous to DeepKK.
- [ ] Add multiprocessing by canonical flop.
- [ ] Add checkpoint/resume and resumable per-flop work queue.
- [ ] Add variance-reduction / alternative CFR sampling methods that preserve exact infosets.
- [ ] Export immutable exact base policy + EV reference.
- [ ] Decide whether production base solver remains CFR-family after validation of rake/multiplayer game-theory caveats.

### Exact-state computational feasibility gate

Before any lossy abstraction is allowed, measure the optimized exact path on representative flop textures and player counts.

- [ ] Benchmark exact HU on low/medium/high canonical-hole-count flops.
- [ ] Measure iterations/s, infoset-visits/s, terminal evaluations/s, peak RAM and policy bytes/state.
- [ ] Run 10k -> 50k -> 100k -> larger cross-seed scaling on the same flop.
- [ ] Estimate full 1,755-flop HU wall time from measured texture-weighted throughput.
- [ ] Repeat staged estimates for 3w, 4w and upward only after HU passes.
- [ ] If exact compute is expensive, optimize implementation before reducing state fidelity.
- [ ] Lossy abstraction may be reconsidered only after this gate documents that exact-state solving is impractical within project resources.

## P4 — Solver validation

Status: **NEXT CRITICAL GATE**

- [x] First 10k HU cross-seed pilot executed; result unstable because median exact-state visits were only ~8.
- [ ] Higher-visit cross-seed policy stability on exact infosets.
- [ ] Mean/max positive regret or the appropriate chosen-solver convergence metric.
- [ ] Best-response/exploitability or equivalent response metric for HU.
- [ ] Multiplayer response/robustness metrics for N>2.
- [ ] EV confidence/error intervals.
- [ ] Coverage/min-visits report per exact canonical state.
- [ ] Exact-vs-sampled equity regression tests.
- [ ] Reproducible run manifest and SHA256 hashes.
- [ ] Validate the target-solution implications of path-dependent rake.
- [ ] Validate the target-solution implications of multiplayer general-sum play before claiming equilibrium properties for N>2.

## P5 — Operational exact base-policy format

- [ ] Define policy key: variant | players | scenario | canonical_flop_hole_id.
- [ ] Compact per-flop/indexed lookup format suitable for OpenHoldem DLL runtime.
- [ ] Quantify probability quantization error if policy probabilities are stored as uint8/uint16.
- [ ] Preserve mathematical policy separately from operational policy.
- [ ] Safe unknown-state fallback.
- [ ] Version policy by complete economic configuration.
- [ ] Do not merge strategically distinct states in the operational export.

## P6 — OpenHoldem base runtime

This is intentionally brought before exploitation. The first live DeepPot must be able to play **base strategy only**.

- [ ] Pot Fold tablemap/scraper validation.
- [ ] Dynamic 2–8 player action-order mapping with BTN last.
- [ ] Formula scenario detection.
- [ ] Exact canonical flop+hole runtime key.
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
- [ ] OpponentStats by variant/player-count/scenario and an exact-state or separately validated statistical feature model.
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
- [ ] Exact PLO state-space/canonicalization study before any abstraction decision.
- [ ] Separate strategies and validation artifacts.
