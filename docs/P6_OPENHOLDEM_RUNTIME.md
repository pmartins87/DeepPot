# P6 — DeepPot mathematical base -> OpenHoldem runtime

Date: 2026-09-08

## Objective

Turn the immutable DeepPot mathematical Base produced by the Ryzen run into a live OpenHoldem decision lookup **without changing a single strategic decision**.

The DeepKK architecture is preserved conceptually:

`explicit situation -> membership in that situation's aggressive-action list -> aggressive action, otherwise fold`

DeepKK can store its 169-class preflop lists directly in OpenPPL. DeepPot cannot, because the strategy key is an exact flop-relative state. DeepPot therefore keeps the same 494-list semantics and replaces only the physical membership representation with dense exact bitsets.

## Immutable mathematical side

The P4 production run produces, for each N=2..8:

- 1,755 canonical flop checkpoints;
- final exact FOLD/STAY bitsets;
- solver-average bitsets;
- confidence bitsets;
- low-coverage bitsets;
- exact flop metadata/indexes;
- audit summaries;
- run manifest and hashes.

There are 494 public decision scenarios total and 635,675,248 exact information-set decisions across N=2..8.

Only the **final** action bitsets are required to play. Solver/confidence/coverage vectors remain with the mathematical source for audit and provenance.

## Runtime compilation

After P4 is completed, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\build_deeppot_runtime.ps1
```

The script refuses to compile a partial mathematical run. It calls `deeppot.runtime_package`, verifies completed N2..N8 indexes and bitset sizes/hashes, and emits:

```text
runs\deeppot_runtime\
    deeppot_runtime_index.bin
    deeppot_runtime_manifest.json
    DeepPot_operational_DISABLED.txt
    strategy\
        N2_final.bits
        N3_final.bits
        ...
        N8_final.bits
```

`DeepPot_operational_DISABLED.txt` is intentionally generated with `f$deeppot_live_enabled=false`. The `BetPot` token present in the disabled draft is syntactically valid OpenPPL but **is not yet accepted as the live Pot Fold STAY-button mapping**. That must be established from the actual table/tablemap before enabling play.

## Exact runtime key

For a live decision, the runtime reconstructs:

1. `N`: players dealt, 2..8;
2. fixed postflop actor index: dealt seats clockwise after BTN, BTN last;
3. prior binary action history: each prior actor is FOLD or STAY;
4. `scenario_dense_id`, exactly matching the trainer;
5. hero hole cards and the three flop cards;
6. exact global-suit canonical flop;
7. exact flop-relative hole-state ID;
8. bit address inside the final strategy vector.

For a fixed N/flop:

`key = scenario_dense_id * hole_state_count + exact_hole_state_id`

and the bit is:

- `1`: STAY;
- `0`: FOLD.

No solver, equity calculation, card bucket or approximation runs while playing.

## One DLL query only

The OpenHoldem user-DLL symbol engine caches the result of `ProcessQuery()` for an action orbit and does not maintain separate cached results for multiple user `dll$` query names. Therefore DeepPot intentionally exposes only:

`dll$deeppot_action`

The return value carries both scenario identity and action:

- `0`: invalid/unknown state -> fail closed;
- `+1 .. +494`: STAY; magnitude identifies the public scenario;
- `-1 .. -494`: FOLD; magnitude identifies the public scenario.

Scenario offsets are frozen:

| N | global zero-based offset | scenarios |
|---:|---:|---:|
| 2 | 0 | 2 |
| 3 | 2 | 6 |
| 4 | 8 | 14 |
| 5 | 22 | 30 |
| 6 | 52 | 62 |
| 7 | 114 | 126 |
| 8 | 240 | 254 |

Thus the signed magnitudes cover exactly 1..494.

## DeepKK-like operational TXT

`src/deeppot/openholdem_formula.py` generates an explicit formula with:

- 494 `f$sit_*` functions;
- 494 `f$list_*_STAY` membership functions;
- one explicit flop router;
- FOLD as the default outside the current scenario's STAY membership;
- one DLL query only.

The named `f$list_*_STAY` functions are the operational equivalents of DeepKK's handlists. Their membership condition is the signed return code from the exact bitset lookup rather than native 169-class OpenPPL handlist syntax.

## Portable C++ lookup core

`runtime/deeppot_runtime_core.{h,cpp}` is the runtime implementation independent of OpenHoldem. It performs:

- runtime package loading;
- exact 24-permutation suit canonicalization;
- canonical-flop lookup;
- flop stabilizer calculation;
- exact flop-relative hole-state enumeration in trainer-compatible order;
- dense scenario calculation;
- exact bit lookup;
- signed action encoding.

A regression test compiles this C++ implementation and compares it against the Python reference lookup on the same exact state. This protects the most dangerous integration boundary: Python trainer state IDs versus C++ live state IDs.

## OpenHoldem adapter

`runtime/openholdem/deeppot_userdll.cpp` adapts OpenHoldem symbols to the portable lookup core. It uses native symbols for:

- `ismyturn`;
- `betround`;
- `ncommoncardsknown`;
- `nchairs`;
- `dealerchair`;
- `userchair`;
- `playersdealtbits`;
- `playersplayingbits`;
- `foldbits2`;
- `nplayersdealt`;
- `$$pr0`, `$$pr1`, `$$ps0`, `$$ps1`;
- `$$cr0..2`, `$$cs0..2`.

The adapter logs either a deterministic `HIT` including N/actor/scenario/flop/hole/action or a `MISS` explaining why it failed closed.

## What remains genuinely live-dependent

Do not guess these from solver code:

1. Pot Fold KKPoker tablemap/scraper must correctly identify dealt/playing/folded seats, BTN, hero and cards.
2. The actual client button corresponding to the fixed STAY/POT payment must be mapped and verified. `BetPot` is only the current disabled OpenPPL placeholder.
3. At least one live hand must confirm that the OpenHoldem seat/action-history reconstruction matches the game UI.

These are integration facts, not solver questions.

## P7 equivalence gate

After the full P4 output exists and the Windows DLL build is available, perform one exhaustive mathematical-to-runtime equivalence pass:

- every supported exact key resolves;
- runtime action equals mathematical final bit;
- zero unknown supported keys;
- zero action mismatches;
- DLL and runtime package hashes recorded.

No second solver-method ladder is introduced by P6/P7.
