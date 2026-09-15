# DeepPot Status

Reference date: 2026-09-14

## Current production base

**Production-selected base: V2_SEL3500 greedy.**

The finite base-policy robustness gate (D3) and the dedicated SEL3500 mathematical-to-runtime release-equivalence gate (D4) have both passed.

Do not run SEL4000 now.

## Exact game/runtime status

- N=2..8 supported;
- 1,755 canonical flops;
- 494 exact public scenarios;
- 635,675,248 exact infosets;
- no strategic card abstraction;
- exact runtime lookup through `DeepPot.txt + user.dll + DeepPotRuntime`;
- i5 remains the live KKPoker/OpenHoldem machine;
- Ryzen 9 remains the solver/analysis/release machine.

Base v1 is still immutable and archived under the P5 freeze SHA256:

`4d4077796ce81ec4d74a99818d69cc999221ad77c973c7d6fe7d4102d1a43a8a`

## Continuous deep track

Canonical root:

`C:\DeepPot\runs\continuous_master_fast_v2`

Kernel: `FastChanceSampledCFRV2`.

The one resumable trajectory has passed:

- 1000 minimum visits for every exact infoset;
- 1500 global minimum;
- 2000 global minimum;
- selective 2500 on 3,541 unstable tasks;
- selective 3000 on 1,756 tasks;
- selective 3500 on 329 tasks.

SEL3000 -> SEL3500:

- 1,386,540 action changes;
- 0.218121% global change;
- N2–N5: 0%;
- N6: 0.0139%;
- N7: 0.0768%;
- N8: 0.3827%;
- only 49/12,285 `(N, flop)` tasks remain above 2% change;
- none remain above 2.5%.

Additional depth is paused because the robustness gate did not reveal a convergence problem that justifies SEL4000.

## Mixing structure

Full SEL3500 scan over all 635,675,248 infosets:

- average CFR near-pure <=1%/>=99%: 8.030%;
- average CFR mixed 10–90: 40.917%;
- average CFR 30–70: 12.016%;
- average CFR 40–60: 5.542%;
- average CFR 45–55: 2.723%;
- current regret-matching near-pure: 50.185%;
- current regret-matching mixed 10–90: 32.237%;
- average-greedy vs current-greedy side disagreement: 4.823%.

Among average-CFR 10–90 states, 77.49% remain mixed in current regret matching. Therefore the average mix is not merely stale averaging residue.

## CFR frequency vs EV alignment

A stratified SEL3500 audit tested whether the CFR majority action also tends to be the EV-best pure action against opponents using the SEL3500 mixed CFR profile.

Point-estimate match by majority band:

- 50–55%: 40.0%;
- 55–60%: 56.7%;
- 60–70%: 68.3%;
- 70–80%: 77.4%;
- 80–90%: 96.7%;
- 90–95%: 100%;
- 95–99%: 100%;
- 99–100%: 100%.

Overall:

- eligible states: 491;
- statistically confident: 243;
- majority action matches point-estimate EV-best: 80.86%;
- among confident states: 97.12%;
- mean EV(greedy)-EV(mixed) vs the CFR profile: +0.06636 ante/hand;
- Pearson `p(STAY)` vs `EV(STAY-FOLD)`: 0.7459.

This audit supported the greedy hypothesis but was not the final release criterion.

## Base-policy robustness gate — D3 PASS

Frozen protocol:

`docs/BASE_POLICY_ROBUSTNESS_GATE_20260914.md`

Formal result:

`docs/BASE_POLICY_ROBUSTNESS_RESULT_20260914.md`

Protocol actually run:

- 28 tasks = 4 canonical flops per N=2..8;
- 1,500 common-random deals/task;
- Hero candidates: mixed, greedy, hybrid60/70/80/90;
- opponent families: cfr_mixed, cfr_greedy, tight, loose, sharpened, flattened, early_tight_late_loose, early_loose_late_tight;
- gross rake 2% provisional;
- +0.70% Hero cashback on contribution;
- read-only: no solver/runtime state modified.

### Winning candidate: greedy

EV delta vs mixed CFR:

- mean: **+0.10162 ante/hand**;
- worst population: **+0.09600**;
- worst N: **+0.02219**;
- cells > 0: **100.0%**;
- significant positive cells: **100.0%**;
- significant negative cells: **0.0%**;
- mean candidate regret: **0.00137**;
- max candidate regret: **0.01085**.

By N, greedy remained positive from N2 (+0.02219) through N8 (+0.20225). By population, its weakest aggregate was the `tight` family at +0.09600.

Greedy beat every hybrid on mean EV and also had lower mean/max candidate regret. Therefore no hybrid confirmation gate is triggered.

### Production interpretation

- keep **V2_SEL3500 greedy**;
- do not implement mixed/hybrid runtime for the base release;
- do not apply static EV overrides;
- do not run SEL4000 now.

The synthetic opponent families are robustness stress tests, not claims about the actual KKPoker population.

## Static EV/BR policy

The seven high-sample greedy-vs-BR-to-CFR mismatches remain diagnostic only. They are not production overrides.

A static best response is conditional on a specific opponent profile. DeepPot currently lacks an opponent/population database rich enough to claim that the real population follows the CFR profile. Therefore production remains CFR-derived.

Authoritative decision:

`docs/BASE_POLICY_DECISION_20260914.md`

## Rake/rakeback

Solver economics remain provisional:

- gross rake: 2%, uncapped;
- nominal user rakeback: 50%;
- observed live cashback: approximately 0.70% of Hero contribution in the measured sample.

Do not convert this into a 1% gross-rake model. The cashback is player-specific and contribution/PVI-dependent.

## D4 production release-equivalence — PASS / CLOSED

The dedicated SEL3500 verifier was run against the immutable `V2_SEL3500` snapshot.

Result:

- stage: **PASS**;
- exact infosets: **635,675,248**;
- structurally resolvable infosets: **635,675,248**;
- action bit mismatches: **0**;
- index metadata mismatches: **0**;
- unknown supported keys: **0**;
- training stage: `completed`;
- `ready_for_live_v5`: `true`.

Frozen release hashes:

- snapshot manifest: `8c85b90f0493f7fb2913d41059d5d8ba86e1f8fb62e7e53d875adb7909d4c563`;
- runtime manifest: `717c2fd0582e91d293b92fea1fc7355524681976a6856b8c5b6e70e2b3e01158`;
- runtime index: `fb8bff8f21efd253ec6374de920de74d9fa662df673d5cd579f68fad152b6f74`.

This closes the mathematical-policy -> packaged-runtime question for SEL3500 greedy. The packaged runtime is byte-for-byte consistent with the continuous-task greedy source across all exact infosets.

Formal release record:

`docs/PRODUCTION_RELEASE_SEL3500_20260914.md`

## Current final base-bot gate — D5 runtime-only deployment/live smoke

D4 does not validate real scraping. The only remaining base-bot uncertainty is the operational i5 path.

The already-known-good i5 `DeepPot.txt`, `user.dll` and tablemap must remain unchanged for the first SEL3500 deployment. Only the complete `DeepPotRuntime` strategy folder is to be replaced.

Release tools now available:

- `tools/prepare_deeppot_sel3500_deployment.ps1`;
- `tools/verify_deeppot_sel3500_runtime_folder.ps1`.

Ryzen 9 command:

```powershell
cd C:\DeepPot
git pull
powershell -ExecutionPolicy Bypass -File .\tools\prepare_deeppot_sel3500_deployment.ps1
```

Expected package:

`C:\DeepPot\runs\production_release_SEL3500\DeepPot_SEL3500_RUNTIME_ONLY.zip`

The script first requires the local D4 JSON to be PASS and to match the frozen release hashes. It then stages only `DeepPotRuntime`, a hash verifier and a README; no replacement formula or DLL is bundled.

After transfer to the i5:

- hash-verify the transferred runtime;
- close OpenHoldem;
- back up the currently working `DeepPotRuntime`;
- replace only `DeepPotRuntime`;
- reopen with the existing known-good `DeepPot.txt`, `user.dll` and tablemap;
- perform the finite live scrape/action smoke validation.

If an invalid/zero action, wrong N/actor/history or scrape inconsistency appears, roll back the runtime folder before further play.

## Population exploitation

Not started and not yet justified.

The DeepKK exploitation architecture relied on a dedicated opponent/player database, not merely OpenHoldem session logs. For Pot Fold, a meaningful global exploit layer would need structured conditional data and treatment of hidden folded hands. OpenHoldem logs alone are insufficient to reconstruct high-quality population ranges.

Decision: complete D5 first. Only build a population database/exploit layer later if measured deviations suggest enough additional EV to justify the complexity.

## Next action on Ryzen 9

Build the frozen runtime-only deployment ZIP with `tools/prepare_deeppot_sel3500_deployment.ps1`. Do not run SEL4000 and do not replace the i5 formula/DLL/tablemap.
