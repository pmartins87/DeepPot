# DeepPot Ryzen worker benchmark result — 2026-09-08

Target host: Ryzen with 32 logical processors.

Frozen protocol: `docs/RYZEN_WORKER_BENCHMARK_PROTOCOL.md`.

## Result

| workers | wall seconds | jobs/min | sum solve s | sum audit s | sum task s |
|---:|---:|---:|---:|---:|---:|
| 15 | 93.6891077000 | 40.9866215430 | 915.011148200 | 303.111329599 | 1229.119612399 |
| 23 | 62.2138719999 | 61.7225688832 | 977.179140800 | 313.414979000 | 1301.020028500 |
| **31** | **61.8000449000** | **62.1358771860** | 1102.639274001 | 349.895708800 | 1465.818359801 |

Selected workers: **31**.

Selection rule was frozen before results: minimum one-pass wall time; exact tie -> lower worker count.

31 workers beat 23 by 0.4138271 seconds, about 0.665%, and beat 15 by 31.8890628 seconds, about 34.0% lower wall time. No second worker tuning ladder is permitted.

## Production consequence

The official DeepPot Ryzen mathematical-base run uses **31 workers**.

The local benchmark wrote:

- `runs/worker_benchmark/worker_benchmark.json`
- `runs/worker_benchmark/selected_workers.txt`

`tools/run_deeppot_ryzen.ps1` reads `selected_workers.txt` automatically when `-Workers` is not explicitly supplied.

This benchmark changes only CPU parallelism. It does not change solver mathematics, CFR+ configuration, EV/CI95 audit, state representation, economy assumptions, or output semantics.
