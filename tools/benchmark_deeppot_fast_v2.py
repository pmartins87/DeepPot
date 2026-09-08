from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from deeppot.cards import Card, enumerate_canonical_flops
from deeppot.fast_solver import FastChanceSampledCFR
from deeppot.fast_solver_v2 import FastChanceSampledCFRV2


def cards_from_key(key):
    return tuple(Card(rank, suit) for rank, suit in key)


def make_solver(cls, n: int, flop, seed: int = 123):
    return cls(
        num_players=n,
        flop=flop,
        rake_pct=0.02,
        rake_cap=None,
        seed=seed,
        cfr_plus=True,
        linear_average=True,
    )


def timed(cls, n: int, flop, iterations: int) -> float:
    solver = make_solver(cls, n, flop)
    solver.solve(100)
    solver = make_solver(cls, n, flop)
    t0 = time.perf_counter()
    solver.solve(iterations)
    return time.perf_counter() - t0


def worker(payload):
    flop_index, iterations, seed = payload
    flop_key = list(enumerate_canonical_flops())[flop_index]
    flop = cards_from_key(flop_key)
    solver = make_solver(FastChanceSampledCFRV2, 8, flop, seed=seed)
    t0 = time.perf_counter()
    solver.solve(iterations)
    wall = time.perf_counter() - t0
    return wall


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--flop-index", type=int, default=877)
    ap.add_argument("--iterations", type=int, default=5000)
    ap.add_argument("--parallel-iterations", type=int, default=3000)
    ap.add_argument("--tasks", type=int, default=62)
    ap.add_argument("--workers", type=int, default=31)
    ap.add_argument("--out", type=Path, default=Path(r"C:\DeepPot\runs\kernel_benchmark_fast_v2\v2.json"))
    args = ap.parse_args()

    flops = list(enumerate_canonical_flops())
    flop = cards_from_key(flops[args.flop_index])

    print("DEEPPOT FAST V1 -> V2 A/B")
    print("  V2 change: scalar prior-path counterfactual reach; no strategy-method change")
    print(f"  flop index: {args.flop_index}")
    print(f"  iterations per implementation/N: {args.iterations:,}")
    rows = []
    for n in (2, 5, 8):
        v1 = timed(FastChanceSampledCFR, n, flop, args.iterations)
        v2 = timed(FastChanceSampledCFRV2, n, flop, args.iterations)
        speedup = v1 / v2
        scenarios = (1 << n) - 2
        nodes_per_s = args.iterations * scenarios / v2
        row = dict(n=n, v1_wall=v1, v2_wall=v2, speedup_v2_vs_v1=speedup, v2_nodes_per_s=nodes_per_s)
        rows.append(row)
        print(f"N={n}  v1={v1:.3f}s  v2={v2:.3f}s  speedup={speedup:.2f}x  v2_nodes/s={nodes_per_s:,.0f}")

    print()
    print(f"DEEPPOT FAST V2 PARALLEL CHECK: workers={args.workers} tasks={args.tasks} N=8")
    task_payloads = []
    # Spread tasks around the canonical-flop catalogue so the workload is not
    # an accidental single-flop special case.
    for i in range(args.tasks):
        fi = (args.flop_index + i * 23) % len(flops)
        task_payloads.append((fi, args.parallel_iterations, 123 + i))

    t0 = time.perf_counter()
    task_walls = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(worker, p) for p in task_payloads]
        for fut in as_completed(futures):
            task_walls.append(float(fut.result()))
    parallel_wall = time.perf_counter() - t0
    total_nodes = args.tasks * args.parallel_iterations * ((1 << 8) - 2)
    parallel_nodes_s = total_nodes / parallel_wall
    print(
        f"workers={args.workers} wall={parallel_wall:.3f}s nodes/s={parallel_nodes_s:,.0f} "
        f"task_mean={sum(task_walls)/len(task_walls):.3f}s task_max={max(task_walls):.3f}s"
    )

    payload = {
        "logical_processors": os.cpu_count(),
        "flop_index": args.flop_index,
        "iterations": args.iterations,
        "single_process": rows,
        "parallel": {
            "workers": args.workers,
            "tasks": args.tasks,
            "iterations_per_task": args.parallel_iterations,
            "wall": parallel_wall,
            "nodes_per_s": parallel_nodes_s,
            "task_mean": sum(task_walls) / len(task_walls),
            "task_max": max(task_walls),
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"JSON: {args.out}")


if __name__ == "__main__":
    main()
