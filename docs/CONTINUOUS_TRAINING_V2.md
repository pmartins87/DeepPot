# DeepPot — Continuous CFR deep-training policy

Reference date: 2026-09-08

Status: **method and infrastructure locked before the long Ryzen run**

This document records the decisions made after reviewing the actual training depth of DeepPot Base v1 against DeepKK. It is the authoritative operating policy for the deeper DeepPot track.

## 1. Why this track exists

Base v1 is complete, frozen and operationally usable, but it is shallow per exact private-state infoset compared with DeepKK.

Base v1 used:

- N=2..8;
- 1,755 canonical flops;
- 494 public scenarios;
- 635,675,248 exact infosets;
- 20,000 CFR+ iterations per fixed flop;
- one sampled complete chance deal per iteration;
- full binary public tree traversal;
- linear averaging;
- seed 123;
- provisional 2% uncapped rake;
- 31 workers.

The full tree traversal produced about 17.34 billion CFR node visits in aggregate, but those visits were spread across 635.7 million exact infosets. The resulting mean was only about **27.28 training visits per exact infoset**.

This is not comparable, per state, with the official DeepKK run. DeepKK used 20,000 iterations x 24,000 deals/iteration = 480 million deals per mode over a vastly smaller 3,718-row strategic state space. The official DeepKK EV audit also used a 5,000-visit minimum; the 25-visit threshold belonged to the quick preset, not the official run.

Therefore Base v1 remains useful but is classified as **complete and operational, materially less deep per exact state than DeepKK**.

## 2. Base v1 is immutable

Nothing in this continuous-training track may overwrite or silently mutate Base v1.

The following remain frozen:

- `runs/deepkk_parity_full`;
- `runs/deeppot_runtime`;
- `runs/p5_freeze`;
- P5 freeze SHA256 `4d4077796ce81ec4d74a99818d69cc999221ad77c973c7d6fe7d4102d1a43a8a`.

The new master lives separately at:

`C:\DeepPot\runs\continuous_master`

## 3. Target is real visit depth, not elapsed time

The first major target is:

> **every one of the 635,675,248 exact infosets must have `visit_count >= 1000`.**

`1000` is a pragmatic first deep target, not a theorem and not a claim of mathematical perfection.

The run does **not** finish merely because 15 days elapsed. It finishes when the actual minimum per-infoset visit count reaches the configured target for every exact state.

Elapsed-time estimates are planning aids only. If policy stability is already extremely high before 1,000, an intermediate snapshot may prove practically sufficient. If policy still changes materially at 1,000, training may continue to 1,500, 2,000 or another justified depth without restarting.

## 4. No mandatory global EV audit for this track

The deep track deliberately does **not** append another huge independent EV/CI audit to every snapshot.

Reason: this track directly increases the quantity that was clearly deficient in Base v1 — CFR training depth per exact infoset — and records the true visit distribution instead of relying on a small audit threshold.

Validation uses:

1. exact `visit_count` distribution;
2. CFR regrets and linear-average strategy sums retained in the resumable state;
3. fraction of average policies near the 45/55 boundary;
4. exact action-bit stability between consecutive snapshots, globally and per N.

Independent EV auditing is not forbidden. It remains available as a **targeted diagnostic** for suspicious hands/spots or if later convergence evidence is ambiguous.

The absence of mandatory global audit must not be interpreted as proof that 1,000 visits makes every action correct. Training visits measure depth; cross-snapshot stability measures whether the learned policy is still moving.

## 5. True CFR resume is mandatory

Base v1 cannot be resumed literally because its compact production artifacts did not preserve the complete CFR state. The continuous master therefore starts a new deterministic trajectory from iteration 1.

The continuous infrastructure persists, per `(N, canonical flop)` task:

- both CFR+ regrets;
- both linear-average `strategy_sum` values;
- exact `visit_count` for every infoset;
- completed global iteration number;
- Python RNG state;
- mathematical source hash;
- configuration hash.

On resume, all of these are restored. Linear averaging continues with the correct global iteration number; RNG continues from the exact saved state.

A regression test verifies that:

`uninterrupted 120 iterations == 45 iterations + save/load + 75 iterations`

for regrets, strategy sums, visits and RNG state.

From this track onward, V1.1 -> V1.2 -> V2 is one continuous mathematical trajectory, not independent retraining.

## 6. Checkpoint model and safe interruption

The master is split into 12,285 independent tasks:

`7 player-count modes x 1,755 canonical flops`.

Tasks are interleaved by flop across N=2..8 so an arbitrary-time snapshot does not spend its first days exclusively deepening low-N modes.

Default checkpoint chunk:

`50,000 additional iterations per task`

Each completed chunk atomically replaces the task's persistent `.dpcfr` state and writes a current greedy-policy bitset and JSON summary.

### Graceful pause

Press **Ctrl+C once** in the training PowerShell.

The parent process then:

- stops launching new chunks;
- lets already-running chunks finish;
- writes their atomic checkpoints;
- writes master stage `paused`;
- prints `SAFE TO CLOSE`.

Only after `SAFE TO CLOSE` should Windows/PowerShell be closed or the Ryzen be shut down.

Running the exact same launcher again resumes the persisted trajectory.

### Unexpected power loss

Atomic replacement means completed checkpoints remain valid. Work since the last completed checkpoint of an active task may be lost, but the prior committed state remains intact. No completed state is intentionally overwritten by partial data.

## 7. Snapshot policy: V1.1, V1.2, V2

The user may freeze a playable snapshot at any safe pause point. Suggested names are:

- `V1.1` around the first useful multi-day checkpoint, e.g. ~5 days;
- `V1.2` around a later checkpoint, e.g. ~10 days;
- `V2` when the configured 1,000-minimum target is reached.

Those day counts are labels/convenience, not mathematical gates.

A snapshot:

- does not consume/reset the training state;
- concatenates the current per-flop greedy linear-average CFR decisions into lossless exact N2..N8 runtime bitsets;
- reuses the already validated exact runtime index;
- creates a dedicated `DeepPot_<snapshot>.txt`;
- creates a runtime manifest and snapshot manifest;
- records exact visit-depth statistics: min, p1, p5, median, mean, p95, max;
- records completed-iteration min/median/max;
- records STAY percentage and 45/55-boundary percentage;
- XOR-compares all 635,675,248 final action bits against the previous snapshot, globally and per N.

After snapshot creation, rerun the master launcher and training continues from the same CFR state.

## 8. Convergence interpretation

Cross-snapshot policy movement is the practical convergence signal.

Example interpretation only:

- V1 -> V1.1: 12% changed;
- V1.1 -> V1.2: 2.1% changed;
- V1.2 -> V2: 0.18% changed.

A rapidly shrinking change rate is evidence that the greedy policy is stabilizing. There is deliberately no predeclared magic percentage that automatically proves optimality; the observed curve will be judged in context, including N-specific concentration and whether changes cluster around near-50/50 average strategies.

If changes remain material at 1,000 visits, the correct action is to **continue the same master**, not start another solver from zero.

## 9. Persistent-state storage

The state keeps four float64 values plus one uint32 visit counter per exact infoset:

- regret FOLD;
- regret STAY;
- strategy-sum FOLD;
- strategy-sum STAY;
- visits.

Nominal payload:

`635,675,248 x 36 bytes ~= 21.31 GiB`

plus headers, summaries, greedy bitsets, atomic temporary files and snapshots.

The launcher requires a 30 GiB free-space safety floor for a new master. After the large fixed-size state has been materialized, resumed sessions use a smaller 2 GiB working-space floor because deeper iterations replace existing state files rather than multiplying their size.

## 10. Reproducibility and source lock

Every persisted task stores a source SHA and task/config SHA. Resume refuses to mix incompatible solver/training code with existing CFR state.

Therefore:

> **Do not `git pull` mathematical solver/continuous-training changes into an active master unless a deliberate migration is prepared.**

Documentation, runtime-only and test-machine work may continue independently, but the mathematical trajectory is source-locked once started.

Seed and economy for this track:

- seed `123`;
- rake `2%`;
- cap `None`;
- economy label remains provisional `2pct-uncapped` until live economics are conclusively resolved.

## 11. Worker count

The Ryzen worker benchmark is already frozen. The continuous launcher reuses:

`31 workers`

from `runs/worker_benchmark/selected_workers.txt` when available. It does not reopen worker-count tuning.

## 12. Operational commands

Start or resume the same master:

```powershell
cd C:\DeepPot
git pull
powershell -ExecutionPolicy Bypass -File .\tools\run_deeppot_continuous.ps1
```

After the master has started, future resumes should normally omit `git pull` and run only the same launcher, preserving the source lock.

Read progress from another PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File C:\DeepPot\tools\status_deeppot_continuous.ps1
```

Pause:

- press `Ctrl+C` once in the training PowerShell;
- wait for `SAFE TO CLOSE`.

Create an arbitrary-time snapshot while safely paused:

```powershell
powershell -ExecutionPolicy Bypass -File C:\DeepPot\tools\snapshot_deeppot_continuous.ps1 -Name V1.1
```

Resume afterward:

```powershell
powershell -ExecutionPolicy Bypass -File C:\DeepPot\tools\run_deeppot_continuous.ps1
```

## 13. Pre-run gate

The long run may start only after:

- repository CI is green;
- dependency-free resume smoke test passes on the Ryzen;
- initial disk safety check passes;
- Base v1 freeze remains untouched.

The smoke command is:

```powershell
python C:\DeepPot\tools\check_deeppot_continuous_resume.py
```

Expected result: `DEEPPOT CONTINUOUS RESUME SMOKE: PASS`.
