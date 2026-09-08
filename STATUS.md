# DeepPot Status

Reference date: 2026-09-08

## Current direction

DeepPot NLH Base v1 is locked to the **same production methodology used for DeepKK**, adapted only for Pot Fold's larger exact postflop state space:

`enumerate all scenarios -> CFR+ -> linear average -> EV/CI95 audit -> immutable exact lists -> operational OpenHoldem -> runtime validation`

Authoritative decision: `docs/DEEPPOT_DEEPKK_METHOD_LOCK.md`.

P4C..P4I are archived research diagnostics and are no longer release blockers. P4I finished and failed its former N=4 gate; no P4J/P4K chain will follow.

## Foundation complete

- mechanics: complete;
- economy: three live observations consistent with 2% gross-pot deduction; cap/profile variation still unconfirmed;
- exact game kernel: PASS;
- 1,755 canonical flops;
- 1,286,792 exact canonical `(flop, hero hole)` states;
- exact 2–8 player public action tree;
- 494 explicit public decision scenarios;
- CFR+ / linear-average solver implemented;
- multiprocessing and resumable per-flop checkpoints implemented;
- DeepKK-style EV/CI95 evaluator implemented;
- compact lossless production audit implemented;
- Windows/Ryzen production launcher implemented;
- finite local worker-count benchmark completed.

## Frozen DeepKK-parity production budget

The first full Ryzen run is configured as:

- N=2 through N=8;
- all 1,755 canonical flops;
- seed 123;
- CFR+ enabled;
- linear averaging enabled;
- **20,000 solver iterations per flop**;
- **50,000 independent EV-audit samples per flop**;
- minimum effective visits for an EV override: **25**;
- confidence rule: `abs(EV_STAY-EV_FOLD) > CI95`;
- inconclusive state: retain solver-average greedy action;
- economy profile recorded explicitly as `provisional-2pct-uncapped` for the first run;
- **31 workers**, selected by the frozen local benchmark.

Measured solve throughput implies about **127 aggregate CPU-hours** for the N=2..8 solve portion. Audit and I/O add further work.

## Worker-count decision — CLOSED

The one allowed local benchmark was completed on the target 32-logical-thread Ryzen using the frozen candidates 15, 23 and 31.

| workers | wall seconds | jobs/min |
|---:|---:|---:|
| 15 | 93.6891 | 40.9866 |
| 23 | 62.2139 | 61.7226 |
| **31** | **61.8000** | **62.1359** |

Result: **31 workers selected**. It beat 23 by about 0.665% and 15 by about 34.0% wall time. No second worker tuning ladder will be run.

Evidence: `docs/RYZEN_WORKER_BENCHMARK_RESULT_20260908.md`.

The local machine already contains `runs/worker_benchmark/selected_workers.txt`, and `tools/run_deeppot_ryzen.ps1` reads it automatically.

## Exact output size and 494 lists

Across N=2..8 the final exact base contains **635,675,248 information-set decisions**.

A literal TXT/CSV expansion would be multi-gigabyte and native OpenPPL handlists cannot represent flop-relative exact states anyway. Production keeps the same DeepKK list semantics while storing membership losslessly as dense bitsets:

- `final`: final STAY/FOLD list membership;
- `solver`: raw solver-average greedy membership;
- `confident`: EV/CI confidence flag;
- `low_coverage`: effective-visit flag.

`DeepPot.txt` contains exactly **494 named STAY-list blocks**, one for every public scenario, and references the matching exact compiled list data. No state bucketing or strategic approximation is introduced.

## Production package

Ready files:

- `src/deeppot/deepkk_style_streaming.py`
- `src/deeppot/deepkk_style_compact.py`
- `src/deeppot/deepkk_style_export.py`
- `src/deeppot/worker_benchmark.py`
- `tools/benchmark_deeppot_workers.ps1`
- `tools/run_deeppot_ryzen.ps1`
- `docs/RYZEN_WORKER_BENCHMARK_PROTOCOL.md`
- `docs/RYZEN_WORKER_BENCHMARK_RESULT_20260908.md`
- `docs/RYZEN_DEEPKK_PARITY_RUN.md`

Regression CI confirms that the compact production audit yields the same final decisions as the row-form DeepKK-style EV/CI evaluator.

## Current active phase

**P4 — official Ryzen mathematical-base run: READY TO START WITH 31 WORKERS.**

From `C:\DeepPot` on the target Ryzen:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_deeppot_ryzen.ps1
```

The launcher reads the already-created 31-worker selection automatically. The run is restart-safe: executing the same command again resumes valid completed flop checkpoints.

After P4 completes, freeze the mathematical source/hashes and proceed directly to the DeepKK-like OpenHoldem operational layer.

## Useful remaining live economy evidence

For a clean Pot Fold payout observation capture:

`players dealt | ante | table/stake label | FOLD/STAY sequence | gross terminal pot | amount awarded | net stack change | separate fee/rake line | jackpot/other fee if present`

Highest-value remaining evidence is one reconstructable multiway hand and one relatively large terminal pot to test whether a rake cap exists. This evidence does not block the provisional-profile Ryzen run.
