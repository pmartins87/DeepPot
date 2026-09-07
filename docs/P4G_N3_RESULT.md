# P4G — N=3 fixed-corpus viability result

Date: 2026-09-07

Frozen protocol: `docs/P4G_FIXED_CORPUS_METHOD_RESET.md`

Workflow run: `34167399145`

Head at execution: `d252f941e6eccf3a3b91e499c0e351686138741b`

## Result

Both predeclared N=3 representative textures passed the unchanged independent unilateral-response gate.

| flop | texture | coverage | seat 0 upper 95% | seat 1 upper 95% | seat 2 upper 95% | result |
|---|---|---:|---:|---:|---:|---|
| `Ah 7d 2c` | rainbow | 1.000000 | 0.021620 | 0.022696 | 0.029529 | PASS |
| `Ah 7h 2h` | monotone | 1.000000 | 0.007285 | 0.009602 | 0.011770 | PASS |

Threshold: every seat unilateral-gain 95% CI upper must be `<= 0.030000 ante`.

The rainbow case is the limiting case. Seat 2 passed by approximately `0.000471 ante`, so this is a real but narrow finite-sample PASS and must not be represented as a large-margin result.

## Independent holdout means

Rainbow:

- seat 0 mean gain: `0.018059`;
- seat 1 mean gain: `0.019893`;
- seat 2 mean gain: `0.026649`.

Monotone:

- seat 0 mean gain: `0.004976`;
- seat 1 mean gain: `0.006986`;
- seat 2 mean gain: `0.009464`.

Each final response estimate used the frozen `250,000` BR-learning sample plus an independent `250,000` holdout sample.

## Fixed-corpus invariants

Optimization used exactly 50,000 chance deals per texture, 32 predictor/corrector rounds, `beta=100`, and radius `0.05/sqrt(round)`.

Corpus hashes:

- rainbow: `4947883248de6c845b581c50e7aa6237189c8dcecad2307631e421eae2378451`;
- monotone: `5285fb118673ee05d78c4278b2a3b238511ee3215623327457140297f7a98e45`.

Across all predictor and corrector stages in both runs, the count of materially negative same-corpus empirical seat gaps was zero. This confirms that the estimator pathology observed in P4F was removed in the frozen P4G execution.

## Artifacts

- `p4g-fixed-corpus-n3_rainbow`, artifact id `10034867976`, digest `sha256:15aa26e7ef26c252d128fc4b406fa6b47f5065fd65bbf5907c0de859038eac50`;
- `p4g-fixed-corpus-n3_monotone`, artifact id `10034910952`, digest `sha256:3b9aa8512e509dc44d9a89d0222b5f7d15b8ee4af9f6501897e0b28410509dc8`.

## Decision

P4G is promoted past the N=3 viability gate. This does **not** close multiway P4. Per the predeclared promotion rule, one N=4..8 scaling schedule must be frozen before any N=4 result is observed, then the existing rainbow/monotone representative gate is executed exactly once for every N=4..8 mode.
