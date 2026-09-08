from __future__ import annotations

import argparse
import cProfile
import io
import json
import os
import pstats
import statistics
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from deeppot.cards import Card, enumerate_canonical_flops
from deeppot.fast_solver import FastChanceSampledCFR


def _cards_from_key(key):
    return tuple(Card(rank, suit) for rank, suit in key)


def _one_task(payload: tuple[int, int, int]) -> dict:
    flop_index, iterations, seed = payload
    flop_key = list(enumerate_canonical_flops())[flop_index]
    flop = _cards_from_key(flop_key)
    solver = FastChanceSampledCFR(
        num_players=8,
        flop=flop,
        rake_pct=0.02,
        rake_cap=None,
        seed=seed,
        cfr_plus=True,
        linear_average=True,
    )
    started = time.perf_counter()
    result = solver.solve(iterations)
    elapsed = time.perf_counter() - started
    return {
        "flop_index": flop_index,
        "iterations": iterations,
        "seconds": elapsed,
        "decision_nodes": iterations * 254,
        "materialized_nodes": len(result.nodes),
    }


def _profile_fast(flop_index: int, iterations: int) -> str:
    flop_key = list(enumerate_canonical_flops())[flop_index]
    flop = _cards_from_key(flop_key)
    solver = FastChanceSampledCFR(
        num_players=8,
        flop=flop,
        rake_pct=0.02,
        rake_cap=None,
        seed=123,
        cfr_plus=True,
        linear_average=True,
    )
    profiler = cProfile.Profile()
    profiler.enable()
    solver.solve(iterations)
    profiler.disable()
    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats("cumtime").print_stats(35)
    return stream.getvalue()


def main() -> int:
    ap = argparse.ArgumentParser(description="Ryzen scaling/profile gate for the mathematically equivalent DeepPot fast CFR kernel")
    ap.add_argument("--iterations", type=int, default=3000)
    ap.add_argument("--tasks", type=int, default=62)
    ap.add_argument("--workers", default="15,23,31")
    ap.add_argument("--profile-iterations", type=int, default=500)
    ap.add_argument("--profile-flop-index", type=int, default=877)
    ap.add_argument("--out", default="runs/kernel_benchmark_fast_scaling")
    args = ap.parse_args()

    workers = [int(x.strip()) for x in args.workers.split(",") if x.strip()]
    if not workers or any(x <= 0 for x in workers):
        raise SystemExit("workers must contain positive integers")
    if args.iterations <= 0 or args.tasks <= 0 or args.profile_iterations <= 0:
        raise SystemExit("iterations/tasks/profile-iterations must be > 0")

    flops = list(enumerate_canonical_flops())
    if not 0 <= args.profile_flop_index < len(flops):
        raise SystemExit("invalid profile flop index")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    print("DEEPPOT FAST-KERNEL RYZEN SCALING GATE")
    print("  exact method: CFR+ | linear average | no abstraction | 2% uncapped | N=8")
    print(f"  logical processors: {os.cpu_count()}")
    print(f"  tasks per candidate: {args.tasks}")
    print(f"  iterations per task: {args.iterations:,}")
    print(f"  worker candidates: {workers}")
    print()

    # Fixed task list for every candidate so worker-count comparisons are fair.
    task_payloads = []
    for i in range(args.tasks):
        flop_index = (args.profile_flop_index + i * 23) % len(flops)
        task_payloads.append((flop_index, args.iterations, 900_000 + i))

    rows = []
    total_nodes = args.tasks * args.iterations * 254
    for w in workers:
        started = time.perf_counter()
        task_seconds = []
        with ProcessPoolExecutor(max_workers=w) as pool:
            futures = [pool.submit(_one_task, p) for p in task_payloads]
            for fut in as_completed(futures):
                task_seconds.append(float(fut.result()["seconds"]))
        wall = time.perf_counter() - started
        row = {
            "workers": w,
            "wall_seconds": wall,
            "decision_nodes": total_nodes,
            "decision_nodes_per_second": total_nodes / wall,
            "task_seconds_mean": statistics.mean(task_seconds),
            "task_seconds_median": statistics.median(task_seconds),
            "task_seconds_max": max(task_seconds),
        }
        rows.append(row)
        print(
            f"workers={w:2d} wall={wall:.3f}s nodes/s={row['decision_nodes_per_second']:,.0f} "
            f"task_mean={row['task_seconds_mean']:.3f}s task_max={row['task_seconds_max']:.3f}s"
        )

    best = min(rows, key=lambda r: r["wall_seconds"])
    print()
    print(f"WINNER workers={best['workers']} wall={best['wall_seconds']:.3f}s nodes/s={best['decision_nodes_per_second']:,.0f}")

    print()
    print(f"Profiling fast N=8 kernel for {args.profile_iterations:,} iterations...")
    profile_text = _profile_fast(args.profile_flop_index, args.profile_iterations)
    (out / "profile_fast_N8.txt").write_text(profile_text, encoding="utf-8")

    payload = {
        "format": "DeepPot fast-kernel Ryzen scaling gate",
        "method": "exact CFR+ / linear average / no abstraction / 2% uncapped",
        "tasks_per_candidate": args.tasks,
        "iterations_per_task": args.iterations,
        "profile_iterations": args.profile_iterations,
        "worker_candidates": workers,
        "rows": rows,
        "winner_workers": best["workers"],
        "winner_wall_seconds": best["wall_seconds"],
        "winner_decision_nodes_per_second": best["decision_nodes_per_second"],
    }
    (out / "scaling.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    print(f"JSON: {out / 'scaling.json'}")
    print(f"Fast profile: {out / 'profile_fast_N8.txt'}")
    print("\n--- FAST N8 cProfile top cumulative functions ---")
    print(profile_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
