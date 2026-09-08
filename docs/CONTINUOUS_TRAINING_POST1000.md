# DeepPot continuous training — continuation beyond 1,000 visits

Reference date: 2026-09-08

This note records the operational decision that the `1,000`-visit threshold is **not a terminal mathematical limit**. It is only the first major depth target for the persistent `continuous_master` CFR trajectory.

## Rule

When every exact infoset reaches `visit_count >= 1000`, the trainer may stop because the configured target has been satisfied. If deeper training is desired, **do not restart from zero and do not create a new solver trajectory**.

Raise only the target and resume the same persistent master state.

Examples:

```powershell
powershell -ExecutionPolicy Bypass -File C:\DeepPot\tools\run_deeppot_continuous.ps1 -TargetMinVisits 1500
```

or:

```powershell
powershell -ExecutionPolicy Bypass -File C:\DeepPot\tools\run_deeppot_continuous.ps1 -TargetMinVisits 2000
```

The existing `.dpcfr` states retain and resume the exact CFR+ trajectory, including regrets, linear-average strategy sums, exact per-infoset visit counts, completed iteration number and RNG state.

`TargetMinVisits` is a stopping/depth criterion, not part of the mathematical solver configuration. Raising it therefore does not invalidate the existing compatible CFR state.

## Source-lock requirement

Once the continuous master has started, do not run `git pull` that changes mathematical solver/training code before resuming it, unless a deliberate state migration has been prepared. The persisted task state is source-hash locked specifically to prevent incompatible continuation.

## Versioning interpretation

Snapshots such as V1.1, V1.2 and V2 are immutable playable photographs of the same evolving master trajectory. Reaching 1,000 visits does not require that the master be discarded. A later V2.1/V3 or other deeper snapshot can be produced after raising the target to 1,500, 2,000, 5,000 or another justified depth.

The decision to continue beyond 1,000 should be based primarily on policy stability between snapshots and the remaining concentration of near-50/50 average policies, not on elapsed time alone.
