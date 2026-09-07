# DeepPot

DeepPot is the Pot Fold branch of the DeepPoker project: a solver-driven strategy, opponent-modeling pipeline, and OpenHoldem runtime for KKPoker Pot Fold.

The project reuses the **architecture and engineering lessons** of DeepKK/AoF, but not its 169-hand preflop state model. Pot Fold begins on a visible flop, so the baseline policy must be conditioned on the public flop, hero hole cards, position, player count, and previous Pot/Fold actions.

## Target architecture

1. **Evidence + economy gate** — freeze the exact KKPoker rules, ante schedule, rake/cap, rakeback/PVI assumptions, and table sizes.
2. **Game kernel** — deterministic Pot Fold action tree and terminal payouts.
3. **Equity engine** — NLH first; exact/sampled turn-river runouts with suit-isomorphic caching.
4. **DeepPot base solver** — equilibrium-oriented baseline, solved per canonical flop class and action history.
5. **Validation** — cross-seed stability, best-response/regret checks, EV confidence, deterministic manifests and hashes.
6. **Tracker + state reconstruction** — reconstruct opponent Pot/Fold actions from OpenHoldem frames.
7. **Opponent model** — aliases, action-level statistics, pool priors and shrinkage.
8. **Exploit layer** — HU/VS1 first, then multiway exact-vector catalog; safe fallback to DeepPot base.
9. **Runtime** — OpenHoldem/OpenPPL + DLL lookup with fail-closed behavior.
10. **Extensions** — PLO4/PLO5 after the NLH pipeline is stable.

## Current scope

- Variant: **NLH Pot Fold first**.
- Player counts: parameterized until the live KKPoker lobby/table sizes are confirmed.
- Core rules: sourced from KKPoker's official Pot Fold page published 2026-09-03.
- Rake: **not yet frozen**. As of project initialization, KKPoker's official general rake page does not contain a Pot Fold-specific table. The engine must therefore keep rake and caps parameterized until verified in the lobby or in an updated official source.

## Design principles inherited from DeepKK

- Base mathematical strategy is immutable once published.
- Exploitation is a separate layer and must never silently replace the base.
- Unknown/mismatched state => **fallback**, never approximation by a nearby unrelated state.
- Every run emits a manifest, config, hashes and validation artifacts.
- Opponent aliases and action reconstruction are auditable and reversible.
- A new economy (rake/cap/ante/game rule) creates a new strategy version.

See [`ROADMAP.md`](ROADMAP.md), [`STATUS.md`](STATUS.md), and [`docs/RULES_ECONOMY.md`](docs/RULES_ECONOMY.md).
