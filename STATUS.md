# DeepPot Status

Reference date: 2026-09-08

## Current direction

DeepPot NLH Base v1 is locked to the **same production methodology used for DeepKK**, adapted only for Pot Fold's larger exact postflop state space:

`enumerate all scenarios -> CFR+ -> linear average -> EV/CI95 audit -> immutable exact lists -> operational OpenHoldem -> runtime validation`

Authoritative decision: `docs/DEEPPOT_DEEPKK_METHOD_LOCK.md`.

P4C..P4I are archived research diagnostics and are no longer release blockers. No P4J/P4K chain will follow.

## P4 mathematical base — RUNNING

The official target-Ryzen run has been started from `C:\DeepPot` with the frozen configuration:

- N=2..8;
- all 1,755 canonical flops per mode;
- seed 123;
- CFR+ + linear average;
- 20,000 solver iterations/flop;
- 50,000 independent EV-audit samples/flop;
- minimum effective visits 25;
- confident EV-best else solver-average greedy fallback;
- provisional economy `provisional-2pct-uncapped`;
- **31 workers** selected by the frozen local benchmark.

Output root: `C:\DeepPot\runs\deepkk_parity_full`.
The run is checkpoint/restart safe.

## Worker benchmark — CLOSED

| workers | wall seconds | jobs/min |
|---:|---:|---:|
| 15 | 93.6891 | 40.9866 |
| 23 | 62.2139 | 61.7226 |
| **31** | **61.8000** | **62.1359** |

31 is frozen. No second worker tuning ladder.

## Exact strategy representation

The complete N=2..8 base contains **635,675,248 exact information-set decisions** over 494 public decision scenarios.

Final live membership is stored losslessly as dense bitsets: one bit per exact state, 1=STAY and 0=FOLD. Solver/confidence/low-coverage bitsets remain separately available for audit. No bucketting or strategic card abstraction is introduced.

## P6 OpenHoldem — IN PROGRESS WHILE P4 RUNS

The runtime-independent part has now advanced substantially:

- `src/deeppot/runtime_contract.py`: one signed action/scenario code for all 494 scenarios;
- `src/deeppot/runtime_package.py`: verifies and compiles completed mathematical output into the minimal live package;
- `src/deeppot/openholdem_formula.py`: generates the DeepKK-like operational TXT with 494 explicit situations and 494 explicit logical STAY-list membership functions;
- `runtime/deeppot_runtime_core.{h,cpp}`: portable C++ exact canonicalization/index/bit lookup;
- `runtime/openholdem/deeppot_userdll.cpp`: OpenHoldem adapter with one `dll$deeppot_action`, deterministic HIT/MISS logs and fail-closed behavior;
- `tools/build_deeppot_runtime.ps1`: one post-training command to compile the completed mathematical base into the live runtime package and safe-disabled formula;
- `docs/P6_OPENHOLDEM_RUNTIME.md`: operational architecture and remaining live gates.

Regression tests cover:

- exact runtime scenario IDs versus trainer IDs;
- signed codes exactly ±1..±494;
- 494 situation + 494 STAY-membership formula structure;
- mathematical-run -> runtime-package compilation;
- Python-reference versus compiled C++ lookup on the same exact flop/hole/scenario state.

DeepPot CI passed the C++/Python lookup test before the OpenHoldem adapter integration. The current OpenHoldem adapter additionally normalizes OpenHoldem suit values Clubs=1..Spades=4 to DeepPot c=0..s=3.

## Isolated OpenHoldem branch

A dedicated branch now exists in `pmartins87/myoh_private`:

`deeppot_runtime_v1`

It is isolated from the existing OpenOFC/default development. On that branch:

- the generic demo `user.cpp` has been replaced by the DeepPot adapter;
- `deeppot_runtime_core.{h,cpp}` has been added to `DLLs/User_DLL`;
- `user.vcxproj` includes the runtime core;
- a dedicated Win32 Release `user.dll` GitHub Actions build gate has been added.

The first Windows build attempt reached compilation but the newest Windows runner lacked `atlstr.h` required by OpenHoldem's unchanged helper `OpenHoldemFunctions.cpp`. This is an environment/dependency issue, not a DeepPot lookup failure. The build gate has been moved to the VS2022 Windows runner, which is being used to resolve that single build dependency without changing solver/runtime semantics.

## Remaining P6 facts that must come from the live table

These are intentionally not guessed:

- Pot Fold tablemap/scraper;
- actual KKPoker chair numbering and BTN/action-order orientation;
- confirmation that `playersdealtbits`, `playersplayingbits` and `foldbits2` reproduce the binary prior FOLD/STAY history correctly;
- actual OpenHoldem action/button mapping that pays the fixed Pot Fold STAY amount.

`BetPot` is currently only a syntactically valid **disabled placeholder**. Generated operational formulas keep `f$deeppot_live_enabled=false` until those items pass shadow validation.

## What happens when P4 finishes

After the running Ryzen process reaches `stage=completed`:

1. freeze mathematical outputs/hashes;
2. update the local repository only after the process has stopped;
3. run `tools/build_deeppot_runtime.ps1`;
4. compile/copy the Win32 DeepPot `user.dll`;
5. validate tablemap and exact live state recognition;
6. perform the single exhaustive mathematical-to-runtime equivalence gate;
7. run exactly 200 shadow decisions;
8. then exactly 200 smallest-stake live autoplayer decisions.

No new solver-method ladder is planned.
