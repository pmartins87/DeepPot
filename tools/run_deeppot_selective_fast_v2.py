from __future__ import annotations

import argparse
import csv
import json
import signal
import statistics
import time
from collections import deque
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from pathlib import Path

from deeppot import continuous_training_fast_v2 as ct
from deeppot.continuous_runner_fast_v2 import production_source_sha256


def _atomic_json(path: Path, payload: dict) -> None:
    ct._atomic_write_json(path, payload)


def _load_plan(csv_path: Path, threshold: float) -> list[tuple[int, int, float]]:
    rows: list[tuple[int, int, float]] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {"n", "flop_index", "changed_pct"}
        if reader.fieldnames is None or not required.issubset(set(reader.fieldnames)):
            raise RuntimeError(f"analysis CSV lacks required columns {sorted(required)}: {csv_path}")
        for row in reader:
            n = int(row["n"])
            flop_index = int(row["flop_index"])
            changed_pct = float(row["changed_pct"])
            if changed_pct > threshold:
                rows.append((n, flop_index, changed_pct))
    rows.sort(key=lambda x: (x[0], x[1]))
    if not rows:
        raise RuntimeError(f"selective plan is empty for changed_pct > {threshold}")
    return rows


def _manifest_payload(
    *,
    root: Path,
    analysis_csv: Path,
    threshold: float,
    target: int,
    chunk: int,
    workers: int,
    selected: list[tuple[int, int, float]],
    summaries: dict[tuple[int, int], dict],
    stage: str,
    started: float,
    source_sha: str,
    stop_reason: str = "",
) -> dict:
    mins = [int(summaries[k].get("visit_min", 0)) for k in summaries]
    reached = sum(v >= target for v in mins)
    return {
        "format": "DeepPot Fast V2 selective continuation",
        "stage": stage,
        "stop_reason": stop_reason,
        "training_root": str(root),
        "analysis_csv": str(analysis_csv),
        "selection_rule": f"changed_pct > {threshold}",
        "changed_pct_threshold": threshold,
        "target_min_visits_selected_tasks": target,
        "chunk_iterations": chunk,
        "workers": workers,
        "source_sha256": source_sha,
        "selected_tasks": len(selected),
        "selected_tasks_target_reached": reached,
        "selected_task_min_global": min(mins) if mins else 0,
        "selected_task_min_median": statistics.median(mins) if mins else 0,
        "started_at_unix": started,
        "updated_at_unix": time.time(),
        "selected": [
            {"n": n, "flop_index": flop_index, "prior_changed_pct": changed_pct}
            for n, flop_index, changed_pct in selected
        ],
    }


def run(args: argparse.Namespace) -> int:
    root = Path(args.training_root).resolve()
    analysis_csv = Path(args.analysis_csv).resolve()
    if not analysis_csv.exists():
        raise RuntimeError(f"analysis CSV not found: {analysis_csv}")
    if args.target_min_visits <= 0 or args.chunk_iterations <= 0 or args.workers <= 0:
        raise ValueError("target/chunk/workers must be positive")

    source_sha = production_source_sha256()
    config = ct.ContinuousConfig(
        seed=args.seed,
        rake_pct=args.rake,
        rake_cap=None,
        cfr_plus=True,
        linear_average=True,
    )
    selected = _load_plan(analysis_csv, args.changed_pct_threshold)
    task_map = {(t.n, t.flop_index): t for t in ct._all_tasks()}

    summaries: dict[tuple[int, int], dict] = {}
    pending: deque[ct.Task] = deque()
    for n, flop_index, _changed in selected:
        key = (n, flop_index)
        task = task_map.get(key)
        if task is None:
            raise RuntimeError(f"analysis selected unknown task N={n} flop={flop_index}")
        s = ct._load_summary(ct.summary_path(root, task))
        if s is None:
            raise RuntimeError(f"selected task lacks persisted summary: N={n} flop={flop_index}")
        if s.get("source_sha256") != source_sha:
            raise RuntimeError(
                f"source-lock mismatch for N={n} flop={flop_index}: "
                f"state={s.get('source_sha256')} current={source_sha}"
            )
        if s.get("task_config_sha256") != ct._task_config_sha256(task, config):
            raise RuntimeError(f"task-config mismatch for N={n} flop={flop_index}")
        summaries[key] = s
        if int(s.get("visit_min", 0)) < args.target_min_visits:
            pending.append(task)

    run_dir = root / "analysis" / (
        f"selective_gt{args.changed_pct_threshold:g}_to_{args.target_min_visits}"
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = run_dir / "SELECTIVE_MANIFEST.json"
    started = time.time()
    stop_requested = False
    stop_reason = ""

    def request_stop(_signum=None, _frame=None) -> None:
        nonlocal stop_requested, stop_reason
        if not stop_requested:
            stop_requested = True
            stop_reason = "user_interrupt"
            print(
                "\nDeepPot SELECTIVE: pause requested. No new chunks will start; "
                "active chunks will finish and checkpoint safely.",
                flush=True,
            )

    previous_handler = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, request_stop)

    initial = _manifest_payload(
        root=root,
        analysis_csv=analysis_csv,
        threshold=args.changed_pct_threshold,
        target=args.target_min_visits,
        chunk=args.chunk_iterations,
        workers=args.workers,
        selected=selected,
        summaries=summaries,
        stage="running",
        started=started,
        source_sha=source_sha,
    )
    _atomic_json(manifest_path, initial)

    print("DeepPot FAST V2 selective exact-CFR continuation")
    print(f"  source lock: {source_sha}")
    print(f"  rule: changed_pct > {args.changed_pct_threshold:g}")
    print(f"  selected tasks: {len(selected):,}/12,285")
    print(f"  selected target: visit_min >= {args.target_min_visits:,}")
    print(f"  chunk: {args.chunk_iterations:,} | workers: {args.workers}")
    print(f"  training root: {root}")
    print("  non-selected tasks are NOT modified")
    print("  each selected (N, flop) resumes its existing CFR/RNG trajectory")

    completed_chunks = 0
    active: dict[object, ct.Task] = {}
    worker_error: BaseException | None = None
    deadline = None if args.max_wall_hours <= 0 else time.monotonic() + args.max_wall_hours * 3600.0

    try:
        with ProcessPoolExecutor(max_workers=args.workers, initializer=ct._worker_init) as pool:
            while pending or active:
                if deadline is not None and time.monotonic() >= deadline and not stop_requested:
                    stop_requested = True
                    stop_reason = "max_wall_hours"
                    print("DeepPot SELECTIVE: wall-time limit reached; draining active chunks.", flush=True)

                while pending and len(active) < args.workers and not stop_requested and worker_error is None:
                    task = pending.popleft()
                    fut = pool.submit(
                        ct.train_one_chunk,
                        (
                            str(root),
                            task,
                            config,
                            source_sha,
                            args.chunk_iterations,
                            args.target_min_visits,
                        ),
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
                        print(f"DeepPot SELECTIVE worker error; draining active chunks: {exc}", flush=True)
                        continue

                    key = (task.n, task.flop_index)
                    summaries[key] = summary
                    completed_chunks += 1
                    if int(summary.get("visit_min", 0)) < args.target_min_visits and not stop_requested:
                        pending.append(task)

                    if completed_chunks % 25 == 0 or int(summary.get("visit_min", 0)) >= args.target_min_visits:
                        p = _manifest_payload(
                            root=root,
                            analysis_csv=analysis_csv,
                            threshold=args.changed_pct_threshold,
                            target=args.target_min_visits,
                            chunk=args.chunk_iterations,
                            workers=args.workers,
                            selected=selected,
                            summaries=summaries,
                            stage="running",
                            started=started,
                            source_sha=source_sha,
                            stop_reason=stop_reason,
                        )
                        _atomic_json(manifest_path, p)
                        print(
                            f"  chunks={completed_chunks:,} selected_target="
                            f"{p['selected_tasks_target_reached']:,}/{len(selected):,} "
                            f"selected_min_global={p['selected_task_min_global']} "
                            f"selected_min_median={p['selected_task_min_median']}",
                            flush=True,
                        )
    finally:
        signal.signal(signal.SIGINT, previous_handler)

    reached = sum(
        int(summaries[k].get("visit_min", 0)) >= args.target_min_visits
        for k in summaries
    )
    if worker_error is not None:
        stage = "error"
    elif reached == len(selected):
        stage = "completed"
        stop_reason = "selected_target_reached"
    elif stop_requested:
        stage = "paused"
    else:
        stage = "paused"
        stop_reason = stop_reason or "queue_drained_without_target"

    final = _manifest_payload(
        root=root,
        analysis_csv=analysis_csv,
        threshold=args.changed_pct_threshold,
        target=args.target_min_visits,
        chunk=args.chunk_iterations,
        workers=args.workers,
        selected=selected,
        summaries=summaries,
        stage=stage,
        started=started,
        source_sha=source_sha,
        stop_reason=stop_reason,
    )
    _atomic_json(manifest_path, final)
    print(f"DeepPot FAST V2 selective stage: {stage.upper()}")
    print(f"  selected target: {final['selected_tasks_target_reached']:,}/{len(selected):,}")
    print(f"  selected min global: {final['selected_task_min_global']}")
    print(f"  selected min median: {final['selected_task_min_median']}")
    print(f"  manifest: {manifest_path}")
    if stage == "paused":
        print("  SAFE TO CLOSE. Rerun the same command to resume the selected tasks.")
    if worker_error is not None:
        raise worker_error
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="Continue only unstable DeepPot Fast-V2 (N, flop) tasks")
    ap.add_argument("--training-root", required=True)
    ap.add_argument("--analysis-csv", required=True)
    ap.add_argument("--changed-pct-threshold", type=float, default=2.0)
    ap.add_argument("--target-min-visits", type=int, default=2500)
    ap.add_argument("--chunk-iterations", type=int, default=50000)
    ap.add_argument("--workers", type=int, default=31)
    ap.add_argument("--seed", type=int, default=123)
    ap.add_argument("--rake", type=float, default=0.02)
    ap.add_argument("--max-wall-hours", type=float, default=0.0)
    args = ap.parse_args()
    raise SystemExit(run(args))


if __name__ == "__main__":
    main()
