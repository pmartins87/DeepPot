# P3 finite exact-state throughput gate — 2026-09-07

## Scope

This is the single N=2..8 engineering throughput gate defined by the Base-v1 roadmap, plus the one allowed implementation-optimization repeat. It does not validate strategy quality and it does not open a benchmark ladder.

Fixed flop: `Ah 7d 2c` (1,176 exact hole states, no strategic abstraction).

Fixed sampled-deal counts:

- N=2: 50,000
- N=3: 20,000
- N=4: 10,000
- N=5: 5,000
- N=6: 2,000
- N=7: 1,000
- N=8: 500

Working economy: provisional 2% rake, uncapped.

## First measurement

| N | iter/s | infoset visits/s |
|---:|---:|---:|
| 2 | 11,029 | 22,058 |
| 3 | 3,487 | 20,920 |
| 4 | 1,335 | 18,694 |
| 5 | 552 | 16,552 |
| 6 | 236 | 14,636 |
| 7 | 105 | 13,177 |
| 8 | 47 | 11,979 |

The high-N drop was traced to repeated exact seven-card evaluation of the same sampled players across many terminal public histories.

## One allowed optimization pass

The solver now computes each player's exact final seven-card rank once per sampled deal and reuses it at every terminal public history. This preserves the exact chance sample, action tree, payoffs, information sets and card-state fidelity.

A regression test compares cached-rank winners against the independent exact showdown path on active-player subsets.

## Fixed benchmark repeated once

| N | iter/s after | infoset visits/s after | speedup |
|---:|---:|---:|---:|
| 2 | 11,806 | 23,612 | 1.07x |
| 3 | 5,557 | 33,342 | 1.59x |
| 4 | 2,659 | 37,224 | 1.99x |
| 5 | 1,314 | 39,429 | 2.38x |
| 6 | 638 | 39,536 | 2.70x |
| 7 | 309 | 38,940 | 2.96x |
| 8 | 147 | 37,243 | 3.11x |

## Decision

**P3 throughput benchmark CLOSED.**

There will be no third throughput benchmark. The production iteration budget is not inferred from throughput alone; it is frozen only after the finite P4 response-quality calibration. The resumable per-flop production runner is already implemented so the eventual 1,755-flop solve can be sharded across the Ryzen 9 and resumed after interruption.
