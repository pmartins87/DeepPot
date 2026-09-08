# DeepPot — Ryzen DeepKK-parity production run

Date: 2026-09-08

## Purpose

This is the production route for DeepPot NLH Base v1. It intentionally follows the DeepKK method rather than the archived P4C..P4I solver-research route.

One command performs:

`exact scenario/flop solve -> CFR+ linear average -> EV/CI95 audit -> solver fallback where inconclusive -> checkpoint -> compact exact lists -> DeepPot.txt + hashes`

## Frozen run configuration

- N=2,3,4,5,6,7,8
- all 1,755 canonical flops
- seed 123
- CFR+ enabled
- linear averaging enabled
- 20,000 solver iterations per flop
- 50,000 independent EV-audit chance samples per flop
- minimum effective visits for EV override: 25
- confidence: `abs(EV_STAY-EV_FOLD) > CI95`
- inconclusive state: keep solver-average greedy action
- economy for this first run: `provisional-2pct-uncapped`
- no strategic card abstraction

## Why the output is bitsets instead of a 600-million-row CSV

Across N=2..8 the exact strategy has **635,675,248 information-set decisions**. Expanding all of those to text would create a multi-gigabyte source file and would not be a native OpenPPL handlist anyway.

The strategy is therefore stored losslessly as dense bitsets:

- `final`: final STAY/FOLD action after the DeepKK-style confidence rule;
- `solver`: raw greedy action of the CFR+ linear-average policy;
- `confident`: whether the EV comparison met the confidence rule;
- `low_coverage`: whether the effective-visit threshold was missed.

`1` in the final bitset means STAY; `0` means FOLD. No states are merged or bucketed.

`DeepPot.txt` still contains the **494 named scenario STAY lists**, mirroring DeepKK's source organization, and points each list to the exact compiled mode data. OpenHoldem later queries the same list through the exact state key.

## Expected compute

Measured solver throughput implies about **127 aggregate CPU-hours** for the 20k-iteration solve over all N and all flops. With a Ryzen 9 using roughly its physical cores in parallel, solve wall time should be in the order of hours. EV audit and disk I/O add further time.

This is only an estimate. The run is checkpointed after every flop, so interruption does not invalidate completed work.

## Windows command

Open PowerShell in the cloned DeepPot repository and run:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_deeppot_ryzen.ps1
```

The script detects the number of logical processors and defaults to approximately physical-core-count minus one worker. To force a worker count:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_deeppot_ryzen.ps1 -Workers 15
```

Optional one-flop environment smoke run:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_deeppot_ryzen.ps1 -Smoke
```

The smoke is optional and is not a new strategic validation phase.

## Resume

If Windows restarts, PowerShell closes, or the run is interrupted, execute the **same full command again**. Completed flop checkpoints with matching source/config hashes are reused automatically.

Do not delete the output directory between runs.

## Output directory

Default:

`runs\deepkk_parity_full`

Main files after completion:

- `DeepPot.txt`
- `scenario_catalog_494.csv`
- `RUN_MANIFEST.json`
- `N2\compiled\N2_final.bits` through `N8\compiled\N8_final.bits`
- matching `*_solver.bits`, `*_confident.bits`, `*_low_coverage.bits`
- `N2\compiled\N2_index.json` through `N8\compiled\N8_index.json`
- per-flop checkpoint `.bin/.json` files for resume/reproducibility
- per-mode `audit_summary.json`

## What to send back after starting

Send the first visible console lines plus the path to `runs\deepkk_parity_full\RUN_MANIFEST.json` (or paste its current contents). From then on, progress is measured by completed flop checkpoints, not by launching new solver-method experiments.
