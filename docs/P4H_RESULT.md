# P4H N=4 result — BLOCKED

Date: 2026-09-07

Frozen workflow: `34173556322`

P4H used deterministic cyclic reverse-seat logit-response continuation on one immutable 50,000-deal corpus, with temperatures `0.16 -> 0.08 -> 0.04 -> 0.02`, 12 reverse-action-order sweeps per temperature, damping 0.50, and the unchanged independent 250k-learn + 250k-holdout response gate.

Both frozen N=4 representative textures failed despite 100% exact-state policy coverage:

| flop | seat 0 upper | seat 1 upper | seat 2 upper | seat 3 upper | result |
|---|---:|---:|---:|---:|---|
| `Ah 7d 2c` rainbow | 0.050204 | 0.070360 | 0.139722 | 0.167616 | FAIL |
| `Ah 7h 2h` monotone | 0.015154 | 0.017002 | 0.041315 | 0.076306 | FAIL |

Frozen threshold: every seat unilateral-gain 95% CI upper <= `0.030000 ante`.

## Diagnostic finding

The failure is not merely a boundary miss. At the final `tau=0.02` stage, the final cyclic sweeps were still making large policy changes. On rainbow, the last sweep's mean absolute per-seat probability updates were approximately `0.0341, 0.0343, 0.0409, 0.0439` depending on seat, with maximum coordinate updates still near `0.48-0.50`. Monotone also retained large maximum updates.

Therefore the frozen P4H iteration was not close to a numerical fixed point of its own final-temperature logit operator. The theoretical binary-logit `tau*log(2)` regret bound is relevant only at a fixed point and cannot be used to excuse the failed holdout result.

## Decision

P4H is **BLOCKED**. We do not add cyclic sweeps, alter damping, alter temperatures, enlarge the corpus, select an intermediate checkpoint, or relax the response threshold.

The next method must change the numerical fixed-point solver rather than extending the P4H ladder.
