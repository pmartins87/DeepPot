# P4E projected Nash extragradient — finite result

Reference date: 2026-09-07

P4E is **BLOCKED**.

The protocol was frozen before results in `docs/P4E_PROJECTED_EXTRAGRADIENT_METHOD_RESET.md`. The promotion condition required both fixed N=3 representative cases to have 100% coverage and every seat unilateral-best-response 95% upper bound <= 0.030000 ante.

## Frozen results

| flop | seat 0 upper | seat 1 upper | seat 2 upper | gate |
|---|---:|---:|---:|---|
| `Ah 7h 2h` monotone | 0.009051 | 0.016615 | 0.016012 | PASS |
| `Ah 7d 2c` rainbow | **0.036877** | 0.019004 | **0.033603** | FAIL |

Coverage was 100% for both cases.

The rainbow final total unilateral-gain estimate was 0.080027 ante with 95% CI `[0.074526, 0.085529]`, but the frozen P4E promotion gate is seat-wise, not the total metric. Seats 0 and 2 independently exceed the unchanged 0.030000 threshold.

## Decision

- do not trigger the already-prepared N=4..8 P4E workflow;
- do not add extragradient rounds;
- do not increase P4E predictor/corrector samples;
- do not change the radius schedule;
- do not select an earlier P4E checkpoint;
- do not relax the response threshold.

The predeclared N=4..8 schedule remains in the repository only as an audit artifact showing that it was frozen before the N=3 outcome; its promotion condition was not met.

P4 therefore moves to a new solver-method reset rather than a P4E tuning ladder.

Source workflow: GitHub Actions run `34160799208`.
