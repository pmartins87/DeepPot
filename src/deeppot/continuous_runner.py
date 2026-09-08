from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import signal
import time
from collections import deque
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from pathlib import Path

from . import continuous_training as ct


RUNNER_VERSION = "2026-09-08.continuous-runner.1"
RESUME_FREE_GIB_FLOOR = 2.0


def production_source_sha256() -> str:
    """Hash every file that can change the resumed mathematical trajectory."""
    h = hashlib.sha256()
    h.update(ct._source_sha256().encode("ascii"))
    h.update(RUNNER_VERSION.encode("ascii"))
    h.update(Path(__file__).read_bytes())
    return h.hexdigest()


def _disk_safety(root: Path, initial_min_free_gib: float) -> tuple[float, float, bool]:
    manifest_exists = (root / "CONTINUOUS_MANIFEST.json").exists()
    free_gib = shutil.disk_usage(root).free / (1024 ** 3)
    required = RESUME_FREE_GIB_FLOOR if manifest_exists else initial_min_free_gib
    if free_gib < required:
        phase = "resume" if manifest_exists else "initial"
        raise RuntimeError(
            f"insufficient free disk for {phase}: {free_gib:.2f} GiB < safety floor {required:.2f} GiB"
        )
    return free_gib, required, manifest_exists


def run_continuous_production(
    *,
    root: Path,
    target_min_visits: int,
    chunk_iterations: int,
    workers: int,
    config: ct.ContinuousConfig,
    max_wall_hours: float,
    min_free_gib: float,
) -> dict:
    if target_min_visits <= 0:
        raise ValueError("target_min_visits must be > 0")
    if chunk_iterations <= 0:
        raise ValueError("chunk_iterations must be > 0")
    if workers <= 0:
        raise ValueError("workers must be > 0")

    root.mkdir(parents=True, exist_ok=True)
    free_gib, required_gib, is_resume = _disk_safety(root, min_free_gib)

    source_sha = production_source_sha256()
    tasks = ct._all_tasks()
    summaries: dict[tuple[int, int], dict] = {}
    pending: deque[ct.Task] = deque()

    for task in tasks:
        s = ct._load_summary(ct.summary_path(root, task))
        if (
            s is not None
            and s.get("source_sha256") == source_sha
            and s.get("task_config_sha256") == ct._task_config_sha256(task, config)
        ):
            summaries[(task.n, task.flop_index)] = s
            if int(s.get("visit_min", 0)) < target_min_visits:
                pending.append(task)
        else:
            # If a state exists but provenance no longer matches, fail before
            # scheduling it. Silently mixing solver versions would corrupt CFR.
            spath = ct.state_path(root, task)
            if spath.exists():
                raise RuntimeError(
                    f"existing CFR state has incompatible/missing summary provenance: {spath}. "
                    "Do not git-pull mathematical training code into an active master."
                )
            pending.append(task)

    started = time.time()
    stop_requested = False
    stop_reason = ""

    def request_stop(_signum=None, _frame=None) -> None:
        nonlocal stop_requested, stop_reason
        if not stop_requested:
            stop_requested = True
            stop_reason = "user_interrupt"
            print(
                "\nDeepPot: pause requested. No new chunks will start; active chunks will finish and checkpoint safely.",
                flush=True,
            )

    previous_handler = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, request_stop)

    manifest = ct._progress_payload(
        root=root,
        summaries=summaries,
        source_sha256=source_sha,
        config=config,
        target_min_visits=target_min_visits,
        chunk_iterations=chunk_iterations,
        workers=workers,
        stage="running",
        started_at_unix=started,
    )
    manifest["runner_version"] = RUNNER_VERSION
    manifest["disk_free_gib_at_start"] = free_gib
    manifest["disk_safety_floor_gib"] = required_gib
    manifest["resume_session"] = is_resume
    ct._write_manifest(root, manifest)

    print("DeepPot CONTINUOUS exact CFR training")
    print(f"  root: {root}")
    print(f"  target: every exact infoset >= {target_min_visits} visits")
    print(f"  chunk: {chunk_iterations:,} iterations per flop-task checkpoint")
    print(f"  workers: {workers}")
    print(f"  tasks: 12,285 | infosets: {ct.TOTAL_EXACT_INFOSETS:,}")
    print(f"  full persistent-state estimate: {manifest['estimated_full_state_gib']:.2f} GiB")
    print(f"  disk free: {free_gib:.2f} GiB | safety floor this session: {required_gib:.2f} GiB")
    print("  Ctrl+C = graceful pause; rerun the same command = exact resume")
    print("  EV audit: disabled by design for this deep track; snapshot stability is measured separately")

    completed_chunks = 0
    deadline = None if max_wall_hours <= 0 else time.monotonic() + max_wall_hours * 3600.0
    active: dict[object, ct.Task] = {}
    worker_error: BaseException | None = None

    try:
        with ProcessPoolExecutor(max_workers=workers, initializer=ct._worker_init) as pool:
            while pending or active:
                if deadline is not None and time.monotonic() >= deadline and not stop_requested:
                    stop_requested = True
                    stop_reason = "max_wall_hours"
                    print("DeepPot: requested wall-time reached; draining active chunks safely.", flush=True)

                while pending and len(active) < workers and not stop_requested and worker_error is None:
                    task = pending.popleft()
                    fut = pool.submit(
                        ct.train_one_chunk,
                        (str(root), task, config, source_sha, chunk_iterations, target_min_visits),
                    )
                    active[fut] = task

                if not active:
                    break

                done, _ = wait(tuple(active), timeout=1.0, return_when=FIRST_COMPLETED)
                if not done:
                    continue

                for fut in done:
                    task = active.pop(fut)
                    try:
                        summary = fut.result()
                    except BaseException as exc:
                        worker_error = exc
                        stop_requested = True
                        stop_reason = f"worker_error:{type(exc).__name__}"
                        print(f"DeepPot worker error; draining remaining active chunks: {exc}", flush=True)
                        continue

                    summaries[(task.n, task.flop_index)] = summary
                    completed_chunks += 1
                    reached = int(summary.get("visit_min", 0)) >= target_min_visits
                    if not reached and not stop_requested and worker_error is None:
                        pending.append(task)

                    if reached or completed_chunks % 25 == 0:
                        p = ct._progress_payload(
                            root=root,
                            summaries=summaries,
                            source_sha256=source_sha,
                            config=config,
                            target_min_visits=target_min_visits,
                            chunk_iterations=chunk_iterations,
                            workers=workers,
                            stage="running",
                            started_at_unix=started,
                            stop_reason=stop_reason,
                        )
                        p["runner_version"] = RUNNER_VERSION
                        ct._write_manifest(root, p)
                        print(
                            f"  chunks={completed_chunks:,} target_tasks={p['tasks_target_reached']:,}/12,285 "
                            f"mean_visits={p['weighted_mean_training_visits']:.2f} "
                            f"task_min_median={p['task_min_visit_median']}",
                            flush=True,
                        )
    finally:
        signal.signal(signal.SIGINT, previous_handler)

    target_reached = sum(
        1 for s in summaries.values() if int(s.get("visit_min", 0)) >= target_min_visits
    )
    if worker_error is not None:
        stage = "error"
    elif target_reached == 12_285:
        stage = "completed"
        stop_reason = "target_reached_all_infosets"
    elif stop_requested:
        stage = "paused"
    else:
        stage = "paused"
        stop_reason = stop_reason or "queue_drained_without_target"

    final = ct._progress_payload(
        root=root,
        summaries=summaries,
        source_sha256=source_sha,
        config=config,
        target_min_visits=target_min_visits,
        chunk_iterations=chunk_iterations,
        workers=workers,
        stage=stage,
        started_at_unix=started,
        stop_reason=stop_reason,
    )
    final["runner_version"] = RUNNER_VERSION
    ct._write_manifest(root, final)

    print(f"DeepPot continuous stage: {stage.upper()}")
    print(f"  target tasks: {final['tasks_target_reached']:,}/12,285")
    print(f"  weighted mean visits: {final['weighted_mean_training_visits']:.2f}")
    print(f"  task min-visit median: {final['task_min_visit_median']}")
    if stage == "paused":
        print("  SAFE TO CLOSE. Run the same command later to resume exactly.")
    elif stage == "completed":
        print("  TARGET COMPLETE: every exact infoset reached the configured minimum visit count.")
    elif stage == "error":
        print("  ERROR state recorded in CONTINUOUS_MANIFEST.json; do not resume until the cause is fixed.")

    if worker_error is not None:
        raise worker_error
    return final


def main() -> None:
    ap = argparse.ArgumentParser(description="DeepPot hardened interruptible/resumable exact CFR deep training")
    ap.add_argument("--out", required=True)
    ap.add_argument("--target-min-visits", type=int, default=ct.DEFAULT_TARGET_MIN_VISITS)
    ap.add_argument("--chunk-iterations", type=int, default=ct.DEFAULT_CHUNK_ITERATIONS)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--seed", type=int, default=123)
    ap.add_argument("--rake", type=float, default=0.02)
    ap.add_argument("--rake-cap", type=float, default=None)
    ap.add_argument("--max-wall-hours", type=float, default=0.0)
    ap.add_argument("--min-free-gib", type=float, default=30.0)
    args = ap.parse_args()

    run_continuous_production(
        root=Path(args.out),
        target_min_visits=args.target_min_visits,
        chunk_iterations=args.chunk_iterations,
        workers=args.workers,
        config=ct.ContinuousConfig(seed=args.seed, rake_pct=args.rake, rake_cap=args.rake_cap),
        max_wall_hours=args.max_wall_hours,
        min_free_gib=args.min_free_gib,
    )


if __name__ == "__main__":
    main()
