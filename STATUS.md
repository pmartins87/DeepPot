# DeepPot Status

Reference date: 2026-09-14

## Current live/research baseline

**Live baseline: V2_SEL3500 greedy.**

Reason for promotion from SEL3000:

- same continuous exact CFR trajectory;
- only 0.218121% of all actions changed from SEL3000;
- no changes at N2–N5;
- only 0.0139% at N6, 0.0768% at N7 and 0.3827% at N8;
- only 49/12,285 `(N, flop)` tasks remain above 2% action change;
- no task remains above 2.5%.

SEL3500 is therefore the deepest, most stable current snapshot. Do not run SEL4000 now.

## Exact game/runtime status

- N=2..8 supported;
- 1,755 canonical flops;
- 494 exact public scenarios;
- 635,675,248 exact infosets;
- no strategic card abstraction;
- exact runtime lookup through `DeepPot.txt + user.dll + DeepPotRuntime`;
- mathematical -> runtime equivalence previously passed with 0 mismatches;
- i5 remains the live KKPoker/OpenHoldem machine;
- Ryzen 9 remains the solver/analysis machine.

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

The selective schedule successfully concentrated CPU on N7/N8 difficult boards. Additional depth is paused because policy selection, not raw CFR depth, is now the main uncertainty.

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

Interpretation: the user's hypothesis is strongly supported outside the marginal 50–60% region, but this is still an audit against CFR-derived opponents, not the real KKPoker population.

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

Rakeback sensitivity audits showed only small action effects concentrated near marginal states; it is not the main current policy-selection issue.

## Current gate — mixed vs greedy vs hybrid

The project is now testing whether the practical greedy projection remains robust when opponents are fixed/non-adaptive but deviate systematically from CFR.

Frozen protocol:

`docs/BASE_POLICY_ROBUSTNESS_GATE_20260914.md`

New tool:

`tools/analyze_policy_robustness_SEL3500.ps1`

Hero candidates:

- mixed;
- greedy;
- hybrid60;
- hybrid70;
- hybrid80;
- hybrid90.

Fixed opponent families:

- CFR mixed;
- CFR greedy;
- tighter;
- looser;
- sharpened;
- flattened;
- early-tight/late-loose;
- early-loose/late-tight.

The gate is finite and read-only. It does not change CFR state, snapshots, DLL, TXT or runtime bitsets.

## Population exploitation

Not started and not yet justified.

The DeepKK exploitation architecture relied on a dedicated opponent/player database, not merely OpenHoldem session logs. For Pot Fold, a meaningful global exploit layer would need structured conditional data and treatment of hidden folded hands. OpenHoldem logs alone are insufficient to reconstruct high-quality population ranges.

Decision: resolve the base policy first. Only build a population database/exploit layer later if measured deviations suggest enough additional EV to justify the complexity.

## Next command on Ryzen 9

```powershell
cd C:\DeepPot
git pull
powershell -ExecutionPolicy Bypass -File .\tools\analyze_policy_robustness_SEL3500.ps1
```

Do not run SEL4000. Do not apply static EV overrides.
