# P4G scaling result — BLOCKED

Date: 2026-09-07

P4G passed its frozen N=3 viability gate, but the frozen N=4..8 scaling workflow then failed immediately at N=4 and again at N=5. This is enough to block P4G as the production method for N>=4. No P4G parameter ladder is allowed.

All completed cases retained 100% exact intended coverage and zero materially negative same-corpus seat-gap stages. The failure is therefore strategic-quality failure under the untouched independent response gate, not a missing-state or estimator-sign bug.

## Completed scaling results

| case | seat 0 upper | seat 1 upper | seat 2 upper | seat 3 upper | seat 4 upper | gate |
|---|---:|---:|---:|---:|---:|---|
| N4 rainbow `Ah 7d 2c` | 0.075952 | 0.058691 | 0.049807 | 0.053125 | — | FAIL |
| N4 monotone `Ah 7h 2h` | 0.036477 | 0.035742 | 0.025135 | 0.023640 | — | FAIL |
| N5 rainbow `Ah 7d 2c` | 0.190325 | 0.146310 | 0.094401 | 0.085317 | 0.054973 | FAIL |
| N5 monotone `Ah 7h 2h` | 0.104327 | 0.076474 | 0.066987 | 0.035960 | 0.030935 | FAIL |

Frozen threshold: every seat unilateral-gain 95% CI upper <= 0.030000 ante.

The N4 rainbow failure is large rather than borderline, and N5 worsens materially. Therefore the finite-roadmap decision is **P4G BLOCKED for N>=4**. We do not add P4G rounds, enlarge its corpus, alter beta/radius, select earlier checkpoints, or relax the gate.

The already-running N6..8 jobs from the same frozen matrix are no longer decision-relevant. Their completion, if GitHub lets them finish, does not reopen P4G.

Next method: P4H deterministic cyclic logit-response continuation, frozen separately before observing any P4H result.
