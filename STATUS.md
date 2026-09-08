# DeepPot Status

Reference date: 2026-09-08

## Current direction

DeepPot NLH Base v1 is locked to the **same production methodology used for DeepKK**, adapted only for Pot Fold's larger exact postflop state space:

`enumerate all scenarios -> CFR+ -> linear average -> EV/CI95 audit -> immutable exact lists -> operational OpenHoldem -> runtime validation`

Authoritative decision: `docs/DEEPPOT_DEEPKK_METHOD_LOCK.md`.

P4C..P4I are archived research diagnostics and are no longer release blockers. No P4J/P4K chain will follow.

## P4 mathematical base — COMPUTE COMPLETED

The official target-Ryzen run finished successfully with `RUN_MANIFEST.json stage=completed` using the frozen configuration:

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

The completed mathematical run was then compiled successfully into the exact OpenHoldem runtime package. The runtime compiler verified `complete=true`, all 1,755 flops, N=2..8 exact bitset lengths/hashes and no strategic card abstraction.

Recorded runtime provenance from the completed target-machine build:

- source `RUN_MANIFEST.json` SHA256: `a1a05a6988ea937ec82a576c7cbf6c7ff2b03ceaa089e448dc3b4756322d5e14`;
- runtime manifest SHA256: `907ce3470bc69c4245abf6e9ecc0f0c88742439af861e3fcf295bdaa7c010686`;
- runtime index SHA256: `fb8bff8f21efd253ec6374de920de74d9fa662df673d5cd579f68fad152b6f74`.

The exact strategy contains **635,675,248 information-set decisions** across N=2..8.

One finite post-run task remains before declaring P4/P5 closed: review the already-produced per-mode confidence/coverage aggregates once and generate the P5 freeze manifest. `tools/freeze_deeppot_p5.ps1` now performs that check and hash freeze without rerunning the solver.

## Worker benchmark — CLOSED

| workers | wall seconds | jobs/min |
|---:|---:|---:|
| 15 | 93.6891 | 40.9866 |
| 23 | 62.2139 | 61.7226 |
| **31** | **61.8000** | **62.1359** |

31 is frozen. No second worker tuning ladder.

## Exact strategy representation

Final live membership is stored losslessly as dense bitsets: one bit per exact state, 1=STAY and 0=FOLD. Solver/confidence/low-coverage bitsets remain separately available for audit. No bucketing or strategic card abstraction is introduced.

Completed live runtime bitsets:

| N | infosets | bytes | SHA256 |
|---:|---:|---:|---|
| 2 | 2,573,584 | 322,465 | `935521d94b04b9db39730ed350202a0a4c38c1f7f8944b848529dac1a4d60635` |
| 3 | 7,720,752 | 965,354 | `9fef40253b5c1831aa9c6f28e696e8d2bf2449ec828ceb0255063ca73bc61328` |
| 4 | 18,015,088 | 2,252,146 | `e03ef203157617d2c3817ee16d0d518a93780f07ba6fe6d5035c6cd54b6a3f17` |
| 5 | 38,603,760 | 4,825,730 | `ce35794830eb61569c065d5ec929328a7a9e5155a04a6f1512fee3960f326fe6` |
| 6 | 79,781,104 | 9,972,898 | `de7b538eaca26fcf73ad0b586f9ec99f446f22118d00dfc00bafaba62a1e8b8a` |
| 7 | 162,135,792 | 20,267,234 | `f0b9c01d45a41baf1c1d469a68171406191206c48fd60d355d8f3b4ac954e9b7` |
| 8 | 326,845,168 | 40,855,906 | `ae74e6b1a4733abf6a7260be0488480f5fc31b80cb510f5b0af7a3cc3ca8de75` |

## P6 OpenHoldem — OFFLINE CORE IMPLEMENTED

Implemented:

- `src/deeppot/runtime_contract.py`: one signed action/scenario code for all 494 scenarios;
- `src/deeppot/runtime_package.py`: verifies and compiles completed mathematical output into the minimal live package;
- `src/deeppot/openholdem_formula.py`: generates the DeepKK-like operational TXT with 494 explicit situations and logical STAY-list membership functions;
- `runtime/deeppot_runtime_core.{h,cpp}`: portable C++ exact canonicalization/index/bit lookup;
- `runtime/openholdem/deeppot_userdll.cpp`: OpenHoldem adapter with one `dll$deeppot_action`, deterministic HIT/MISS logs and fail-closed behavior;
- `tools/build_deeppot_runtime.ps1`: completed successfully against the official run;
- runtime suit normalization from OpenHoldem Clubs=1..Spades=4 to DeepPot c=0..s=3;
- safe-disabled generated formula `C:\DeepPot\runs\deeppot_runtime\DeepPot_operational_DISABLED.txt`.

Regression tests cover exact runtime scenario IDs, signed ±1..±494 codes, formula structure, mathematical-run -> runtime-package compilation and Python-reference versus C++ lookup on the same exact state.

## Isolated OpenHoldem branch / user.dll

Dedicated branch: `pmartins87/myoh_private:deeppot_runtime_v1`.

The actual Win32 Release DeepPot `user.dll` build now **passes** on the VS2022/v143 runner. The successful binary SHA256 recorded by the build is:

`0F939BAC4D5B3E95DCC219D0EC99CCB6FE4B12D97860FFAD5FA01A1E504C1FC9`

The first VS2026 image failure was only a missing legacy ATL dependency; the compatible VS2022 build resolved it without changing DeepPot runtime semantics.

## Remaining P6 facts that must come from the live table

These are intentionally not guessed:

- Pot Fold tablemap/scraper;
- actual KKPoker chair numbering and BTN/action-order orientation;
- confirmation that `playersdealtbits`, `playersplayingbits` and `foldbits2` reproduce the binary prior FOLD/STAY history correctly;
- actual OpenHoldem action/button mapping that pays the fixed Pot Fold STAY amount.

`BetPot` remains only a syntactically valid **disabled placeholder**. `f$deeppot_live_enabled=false` stays frozen until those items pass shadow validation.

## Immediate next gate

1. run `tools/freeze_deeppot_p5.ps1` once on the completed local outputs;
2. record the per-mode confidence/coverage result and P5 freeze-manifest SHA;
3. perform the single P7 exhaustive mathematical-to-runtime key/equivalence gate;
4. then move to live tablemap/state-recognition validation;
5. exactly 200 shadow decisions;
6. exactly 200 smallest-stake live autoplayer decisions.

No new solver-method ladder is planned.
