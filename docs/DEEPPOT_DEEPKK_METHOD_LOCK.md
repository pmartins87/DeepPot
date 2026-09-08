# DeepPot — DeepKK-method lock

Date: 2026-09-08

## Decision

DeepPot NLH Base uses the same production pattern that produced DeepKK, adapted only where Pot Fold postflop necessarily has a much larger exact state space.

This supersedes the idea that P4C/P4D/P4E/P4F/P4G/P4H/P4I exploitability experiments are release blockers. They remain archived diagnostics. There is no P4J/P4K ladder.

## Canonical pattern inherited from DeepKK

1. Enumerate every decision scenario.
2. Train one immutable mathematical base strategy with CFR+.
3. Use linear strategy averaging.
4. Separately evaluate FOLD versus the aggressive action at each information set.
5. Record the EV gap, standard error, CI95, and effective coverage.
6. When the EV comparison is statistically confident, use the EV-best action.
7. When it is inconclusive, retain the greedy action of the solver's linear-average policy.
8. Export immutable mathematical source data plus manifests and SHA256 hashes.
9. Build a separate OpenHoldem operational layer from that immutable base.
10. Add tracking/exploitation only after the base is operational; ambiguity falls back to the base.

This is deliberately the DeepKK pattern rather than a new multiplayer-solver research programme.

## Exact state instead of 169-only postflop abstraction

DeepKK could use `scenario x 169 preflop handclass`. DeepPot cannot safely do that after the flop because the visible board changes the strategic meaning of ranks and suits.

The DeepPot counterpart of DeepKK's handclass is therefore the exact lossless key:

`canonical_flop_index + exact_flop_relative_hole_state_id`.

There are:

- 1,755 canonical NLH flops;
- 1,286,792 exact canonical `(flop, hero hole)` states;
- no strategic card abstraction beyond exact global suit isomorphism.

This changes the state representation, not the training method.

## Scenario catalogue

Every nonterminal fixed-order public FOLD/STAY history is a strategic scenario.

- N=2: 2
- N=3: 6
- N=4: 14
- N=5: 30
- N=6: 62
- N=7: 126
- N=8: 254

Total: **494 strategic scenarios**.

The BTN all-prior-FOLD history is terminal and therefore has no decision.

## Official Ryzen Base-v1 budget

The production budget is now frozen in native DeepPot units:

- players: **N=2 through N=8**;
- canonical flops: **all 1,755**;
- CFR+: **enabled**;
- linear average: **enabled**;
- deterministic solve seed: **123**;
- training: **20,000 solver iterations per canonical flop, for every N**;
- separate EV/CI audit: **50,000 chance samples per canonical flop, for every N**;
- minimum effective visits for an EV-best override: **25**;
- confidence rule: `abs(EV_STAY - EV_FOLD) > CI95` and effective visits >= 25;
- inconclusive rule: retain solver-average greedy action;
- current economy profile for the first run: explicit **`provisional-2pct-uncapped`**;
- checkpoint/resume after every completed flop;
- final manifests and SHA256 hashes.

The 20,000-iteration count intentionally matches the full DeepKK production iteration count. A raw DeepKK `deals_per_iter` is not copied because one DeepPot iteration already samples a complete postflop chance deal and traverses the fixed flop's full public action tree; the two inner-loop units are not equivalent.

The EV audit keeps the same DeepKK statistical decision rule. Its sample count is expressed per canonical flop because DeepPot has a separate exact state space on each board. The minimum override coverage is deliberately finite; low-confidence states are not guessed and remain on the solver-average action, exactly following the DeepKK fallback principle.

## Compute expectation from the already-measured solver throughput

At 20,000 iterations per flop, the measured single-process solver rates imply approximately **127 aggregate CPU-hours** for the N=2..8 solve portion over all 1,755 flops. A Ryzen 9 using roughly its physical cores in parallel should therefore finish the solve in the order of hours rather than days; audit and I/O add additional wall time. This is an estimate, not a release gate.

No extra calibration ladder is inserted before this production run.

## DeepPot.txt and the 494 lists

The conceptual source remains DeepKK-like:

- `##notes##` provenance;
- explicit N/scenario catalogue;
- one named STAY list for each of the 494 strategic scenarios;
- FOLD is the default outside the STAY list;
- no exploitation logic in the mathematical base.

A literal expansion of every exact DeepPot state into text would require **635,675,248 scenario-state decisions** across N=2..8 and would create a multi-gigabyte TXT that OpenPPL could not natively interpret anyway. That would preserve neither practicality nor DeepKK's clean operational separation.

Therefore each named `##list_..._STAY##` in `DeepPot.txt` is backed losslessly by a dense exact-state bitset. The bitset contains one bit per exact information set: `1=STAY`, `0=FOLD`. The matching mode index specifies the flop byte offset and the exact key formula:

`scenario_dense_id * hole_state_count + exact_hole_state_id`.

This is storage compression only. It does not bucket, approximate, or merge strategic states. The final action space still contains all **635,675,248** exact decisions.

The production package also preserves separate solver-greedy, confidence, and low-coverage bitsets so we can audit where the EV/CI layer changed the raw solver decision without writing hundreds of millions of CSV rows.

## Production implementation

Canonical files:

- `src/deeppot/deepkk_style_streaming.py` — resumable all-mode trainer;
- `src/deeppot/deepkk_style_compact.py` — DeepKK-style EV/CI audit with lossless compact output;
- `src/deeppot/deepkk_style_export.py` — 494-scenario catalogue;
- `tools/run_deeppot_ryzen.ps1` — one-command Windows/Ryzen entry point.

The streaming generator solves one flop, audits it, checkpoints compact bitsets, and moves on. It never materializes a 600+ million-row CSV in memory or on disk.

## Archived P4C..P4I research

Keep all code and results for reproducibility. They asked a stronger exploitability/fixed-point question than DeepKK required. They are diagnostics only and do not block the DeepKK-parity route.

## Definition of success for Base v1

DeepPot Base v1 is complete when:

1. the official Ryzen run completes all N=2..8 and all 1,755 canonical flops under the frozen economy profile;
2. the DeepKK-style EV/CI/coverage audit and final exact action bitsets are exported;
3. `DeepPot.txt`, the 494-scenario catalogue, mode indexes, manifests, and hashes are generated;
4. OpenHoldem identifies the same N/scenario/flop/hole key and returns only FOLD or POT/STAY;
5. finite shadow/live checks confirm correct state recognition and legal actions.

Opponent modelling/exploitation begins only after that base is operational.
