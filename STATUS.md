# DeepPot Status

Reference date: 2026-09-08

## Current direction

DeepPot NLH Base v1 remains locked to the **same production methodology used for DeepKK**, adapted only for Pot Fold's much larger exact postflop state space:

`enumerate all scenarios -> CFR+ -> linear average -> EV/CI95 audit -> immutable exact lists -> operational OpenHoldem -> runtime validation`

Authoritative decision: `docs/DEEPPOT_DEEPKK_METHOD_LOCK.md`.

The current frozen Base v1 is now allowed to proceed to live **shadow mode** while a deeper statistical Base v2/audit campaign is prepared separately. Base v1 must not be overwritten.

## P4 mathematical base — COMPLETE

The official target-Ryzen run completed successfully in **22,598.7 s = 6.28 h** with:

- N=2..8;
- all 1,755 canonical flops per mode;
- seed 123;
- CFR+ + linear average;
- 20,000 solver iterations/flop;
- 50,000 independent EV-audit samples/flop;
- minimum effective visits 25;
- confident EV-best else solver-average greedy fallback;
- provisional economy `provisional-2pct-uncapped`;
- 31 workers selected by the frozen local benchmark.

Completed source-run SHA256:

`a1a05a6988ea937ec82a576c7cbf6c7ff2b03ceaa089e448dc3b4756322d5e14`

The exact strategy contains **635,675,248 information-set decisions** across N=2..8.

### Final audit review

| N | infosets | covered | low coverage | confident | confident / adequate | final STAY |
|---:|---:|---:|---:|---:|---:|---:|
| 2 | 2,573,584 | 100% | 0.1602% | 66.3441% | 66.4506% | 80.4089% |
| 3 | 7,720,752 | 100% | 10.3988% | 52.2670% | 58.3329% | 64.6348% |
| 4 | 18,015,088 | 100% | 32.7921% | 37.4199% | 55.6777% | 53.3870% |
| 5 | 38,603,760 | 100% | 50.9822% | 26.5572% | 54.1787% | 45.2988% |
| 6 | 79,781,104 | 100% | 70.7244% | 15.7645% | 53.8487% | 39.7704% |
| 7 | 162,135,792 | 100% | 84.2742% | 8.6108% | 54.7561% | 36.7355% |
| 8 | 326,845,168 | 100% | 91.7877% | 4.6051% | 56.0760% | 36.7748% |

Totals:

- covered at least once: **635,675,248 / 635,675,248 = 100.0000%**;
- low coverage: **519,462,494 = 81.7182%**;
- adequate coverage: **116,212,754 = 18.2818%**;
- confident: **64,326,171 = 10.1193% of all states, 55.3521% of adequately covered states**;
- final STAY: **245,651,878 = 38.6442%**;
- confident EV overrides versus solver-average greedy: **8,307,288**.

Interpretation: low coverage refers to the independent EV/CI audit's effective-visit threshold, not missing CFR training states. Every supported state still has a final action; inconclusive/low-coverage states retain the solver-average greedy action. The high multiway low-coverage rate is the reason a deeper campaign will be prepared in parallel, without delaying Base v1 shadow validation.

## P5 immutable freeze — COMPLETE

Freeze manifest:

`C:\DeepPot\runs\p5_freeze\P5_FREEZE_MANIFEST.json`

SHA256:

`4d4077796ce81ec4d74a99818d69cc999221ad77c973c7d6fe7d4102d1a43a8a`

Do not alter or delete:

- `runs\deepkk_parity_full`;
- `runs\deeppot_runtime`;
- `runs\p5_freeze`.

## Runtime package — COMPLETE

Runtime provenance:

- runtime manifest SHA256: `907ce3470bc69c4245abf6e9ecc0f0c88742439af861e3fcf295bdaa7c010686`;
- runtime index SHA256: `fb8bff8f21efd253ec6374de920de74d9fa662df673d5cd579f68fad152b6f74`;
- `complete=true`;
- 1,755 canonical flops;
- no strategic card abstraction.

Final live membership is stored losslessly as one bit per exact state, 1=STAY and 0=FOLD.

## P6 OpenHoldem — OFFLINE CORE IMPLEMENTED / LIVE SCRAPE VALIDATION NEXT

Implemented:

- exact 494-scenario contract;
- exact runtime index and N2..N8 final bitset loader;
- exact 24-suit-permutation canonicalization and hole-state reconstruction in C++;
- one `dll$deeppot_action` OpenHoldem adapter with deterministic HIT/MISS logging and fail-closed result 0;
- OpenHoldem suit normalization 1..4 -> DeepPot 0..3;
- DeepKK-like operational TXT generator;
- successful Win32 Release `user.dll` build on VS2022/v143;
- safe-disabled operational formula;
- dedicated OpenHoldem branch `pmartins87/myoh_private:deeppot_runtime_v1`.

Successful `user.dll` SHA256:

`0F939BAC4D5B3E95DCC219D0EC99CCB6FE4B12D97860FFAD5FA01A1E504C1FC9`

Still live-dependent:

- validated Pot Fold tablemap/scraper;
- KKPoker chair numbering and BTN/action-order orientation;
- `playersdealtbits` / `playersplayingbits` / `foldbits2` agreement with actual prior FOLD/STAY history;
- actual STAY/POT button action mapping.

## P7 mathematical -> runtime equivalence — PASS

Local exhaustive gate result:

`C:\DeepPot\runs\p7_equivalence\P7_EQUIVALENCE_RESULT.json`

PASS facts:

- structurally resolvable infosets: **635,675,248 / 635,675,248**;
- unknown supported keys: **0**;
- action bit mismatches: **0**;
- index metadata mismatches: **0**;
- source/runtime final SHA256 identical for every N=2..8.

The gate matches all 1,755 source flop records per N to the runtime canonical flop codes and hole-state widths, accounts for every infoset, and XOR-compares the final source/runtime action vectors byte-for-byte. Python-vs-compiled-C++ exact canonicalization/query parity is separately regression-tested.

## P8 shadow mode — PREPARATION IN PROGRESS

A dedicated **no-action** shadow formula and one-command package builder have been added:

- `src/deeppot/openholdem_shadow_formula.py`;
- `tools/prepare_deeppot_shadow.ps1`.

The generated `DeepPot_SHADOW_SAFE.txt` contains no Fold/Call/Bet/Raise/Allin action command. It queries `dll$deeppot_action` only through OpenHoldem's `f$debug` tab. With Autoplayer OFF and Debug -> Auto enabled, OpenHoldem evaluates the recommendation once per heartbeat while the DLL writes `[DeepPot] HIT/MISS` records.

P8 acceptance remains exactly **200 consecutive valid decisions** after tablemap/state recognition is validated.

## Parallel deeper strategy work

Base v1 remains frozen and proceeds to shadow/live validation. In parallel, a deeper statistical campaign may increase independent EV-audit sampling and use a substantially stronger effective-visit threshold, closer in spirit to the DeepKK final audit. Any such output is a separate Base v2 candidate and may not mutate Base v1.
