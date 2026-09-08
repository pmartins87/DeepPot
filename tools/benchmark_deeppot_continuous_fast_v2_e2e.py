from __future__ import annotations

import json
import shutil
import statistics
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from deeppot import continuous_runner_fast_v2 as runner
from deeppot import continuous_training_fast_v2 as ct
from deeppot.state_space import decision_scenario_count


def run_wave(root: Path, tasks: list[ct.Task], chunk: int, workers: int, target: int) -> tuple[float, list[dict]]:
    config = ct.ContinuousConfig(seed=123, rake_pct=0.02, rake_cap=None)
    source_sha = runner.production_source_sha256()
    started = time.perf_counter()
    rows: list[dict] = []
    with ProcessPoolExecutor(max_workers=workers, initializer=ct._worker_init) as pool:
        futures = {
            pool.submit(
                ct.train_one_chunk,
                (str(root), task, config, source_sha, chunk, target),
            ): task
            for task in tasks
        }
        for fut in as_completed(futures):
            rows.append(fut.result())
    wall = time.perf_counter() - started
    return wall, rows


def summarize(label: str, wall: float, rows: list[dict], chunk: int) -> dict:
    nodes = sum(int(r["public_scenarios"]) * chunk for r in rows)
    visit_mins = [int(r["visit_min"]) for r in rows]
    visit_means = [float(r["visit_mean"]) for r in rows]
    chunk_seconds = [float(r["chunk_seconds"]) for r in rows]
    state_bytes = sum(int(r["state_bytes"]) for r in rows)
    out = {
        "label": label,
        "wall_seconds": wall,
        "tasks": len(rows),
        "chunk_iterations": chunk,
        "decision_nodes": nodes,
        "effective_nodes_per_second_including_checkpoint": nodes / wall,
        "visit_min_min": min(visit_mins),
        "visit_min_median": statistics.median(visit_mins),
        "visit_min_max": max(visit_mins),
        "visit_mean_median": statistics.median(visit_means),
        "worker_chunk_seconds_median": statistics.median(chunk_seconds),
        "worker_chunk_seconds_max": max(chunk_seconds),
        "state_bytes_total": state_bytes,
    }
    print(
        f"{label}: wall={wall:.3f}s nodes/s={out['effective_nodes_per_second_including_checkpoint']:,.0f} "
        f"visit_min[min/med/max]={out['visit_min_min']}/{out['visit_min_median']}/{out['visit_min_max']} "
        f"visit_mean_med={out['visit_mean_median']:.2f} state={state_bytes / (1024**2):.1f} MiB"
    )
    return out


def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    root = repo / "runs" / "kernel_benchmark_continuous_fast_v2_e2e"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)

    workers = 31
    chunk = 50_000
    target = 1000
    tasks = [t for t in ct._all_tasks() if t.n == 8][:workers]
    assert len(tasks) == workers

    print("DEEPPOT FAST V2 CONTINUOUS E2E GATE")
    print(f"  workers: {workers}")
    print(f"  representative tasks: {len(tasks)} N=8 flops")
    print(f"  canonical chunk: {chunk:,} iterations")
    print("  wave 1 = fresh train + atomic state/greedy/summary checkpoint")
    print("  wave 2 = load persisted CFR/RNG + continue + atomic replacement checkpoint")
    print("")

    wall1, rows1 = run_wave(root, tasks, chunk, workers, target)
    s1 = summarize("fresh", wall1, rows1, chunk)

    wall2, rows2 = run_wave(root, tasks, chunk, workers, target)
    s2 = summarize("resume", wall2, rows2, chunk)

    iterations_completed = [int(r["iterations_completed"]) for r in rows2]
    visit_mins = [int(r["visit_min"]) for r in rows2]
    projected = [
        (it * target / vm) if vm > 0 else float("inf")
        for it, vm in zip(iterations_completed, visit_mins)
    ]
    finite = [x for x in projected if x != float("inf")]

    # 494 public scenarios summed over N=2..8, for each of 1,755 flops.
    scenario_nodes_per_equal_iteration_depth = 494 * 1755
    e2e_rate = float(s2["effective_nodes_per_second_including_checkpoint"])
    projected_max_iterations = max(finite) if finite else float("inf")
    rough_full_hours = (
        projected_max_iterations * scenario_nodes_per_equal_iteration_depth / e2e_rate / 3600.0
        if finite and e2e_rate > 0
        else float("inf")
    )

    print("")
    if finite:
        print(
            "Representative linear projection from 100k-iteration visit minima: "
            f"median={statistics.median(finite):,.0f} iterations, max={max(finite):,.0f} iterations to min_visit~1000"
        )
        print(
            "Rough all-N/all-flop compute projection at resumed E2E nodes/s "
            f"using the worst of these 31 N8 flops: ~{rough_full_hours:.1f} h."
        )
        print("  This is an estimate only; the canonical trainer stops on measured visit_min, not on elapsed time.")

    payload = {
        "kernel": "FastChanceSampledCFRV2",
        "workers": workers,
        "tasks": len(tasks),
        "chunk_iterations": chunk,
        "fresh": s1,
        "resume": s2,
        "projected_iterations_to_1000_from_100k": finite,
        "projected_iterations_median": statistics.median(finite) if finite else None,
        "projected_iterations_max": max(finite) if finite else None,
        "rough_full_hours_using_projected_max": rough_full_hours if finite else None,
        "source_sha256": runner.production_source_sha256(),
    }
    out = root / "e2e.json"
    out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(f"JSON: {out}")


if __name__ == "__main__":
    main()
