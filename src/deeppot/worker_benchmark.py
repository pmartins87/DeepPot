from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from .cards import Card, enumerate_canonical_flops
from .deepkk_style_compact import evaluate_policy_deepkk_style_compact
from .exact_index import ExactFlopHoleIndex
from .solver import ChanceSampledCFR
from .state_space import decision_scenario_count

BENCHMARK_VERSION = "2026-09-08.1"


def spread_indices(total: int, count: int) -> tuple[int, ...]:
    if total <= 0 or count <= 0 or count > total:
        raise ValueError("invalid total/count")
    if count == 1:
        return (total // 2,)
    values = [round(i * (total - 1) / (count - 1)) for i in range(count)]
    if len(set(values)) != count:
        raise AssertionError("spread index generation produced duplicates")
    return tuple(values)


def default_worker_candidates(logical: int) -> tuple[int, ...]:
    if logical <= 1:
        return (1,)
    candidates = {
        max(1, logical // 2 - 1),
        max(1, (3 * logical) // 4 - 1),
        max(1, logical - 1),
    }
    return tuple(sorted(c for c in candidates if c <= logical))


def _cards_from_key(key: tuple[tuple[int, int], ...]) -> tuple[Card, Card, Card]:
    return tuple(Card(rank, suit) for rank, suit in key)  # type: ignore[return-value]


def _one_job(args: tuple[int, tuple[tuple[int, int], ...], int, int, int]) -> dict:
    flop_index, flop_key, iterations, audit_samples, seed = args
    flop = _cards_from_key(flop_key)

    started = time.perf_counter()
    solved = ChanceSampledCFR(
        num_players=8,
        flop=flop,
        rake_pct=0.02,
        rake_cap=None,
        seed=seed + flop_index * 1009,
        cfr_plus=True,
        linear_average=True,
    ).solve(iterations)
    solve_seconds = time.perf_counter() - started

    exact = ExactFlopHoleIndex.build(flop)
    expected = len(exact) * decision_scenario_count(8)
    partial = solved.average_policy()
    # Benchmark only: fill states not visited by the reduced calibration run with
    # neutral 50/50 so the exact production audit code can be exercised. The
    # official trainer never uses this fill; it requires complete CFR coverage.
    policy = {key: partial.get(key, (0.5, 0.5)) for key in range(expected)}

    audit_started = time.perf_counter()
    audit = evaluate_policy_deepkk_style_compact(
        num_players=8,
        flop=flop,
        policy=policy,
        samples=audit_samples,
        min_effective_visits=0.0,
        seed=seed + 50_000_000 + flop_index * 1009,
        rake_pct=0.02,
        rake_cap=None,
    )
    audit_seconds = time.perf_counter() - audit_started

    return {
        "flop_index": flop_index,
        "hole_states": len(exact),
        "expected_infosets": expected,
        "solve_seconds": solve_seconds,
        "audit_seconds": audit_seconds,
        "total_seconds": time.perf_counter() - started,
        "covered_infosets": audit.summary["covered_infosets"],
    }


def run_worker_benchmark(
    *,
    candidates: tuple[int, ...],
    jobs: int = 64,
    iterations: int = 3000,
    audit_samples: int = 3000,
    seed: int = 123,
) -> dict:
    logical = os.cpu_count() or 1
    candidates = tuple(sorted(set(int(x) for x in candidates)))
    if not candidates or any(x <= 0 or x > logical for x in candidates):
        raise ValueError(f"workers must be between 1 and logical CPU count ({logical})")
    if iterations <= 0 or audit_samples <= 0:
        raise ValueError("iterations/audit_samples must be positive")

    flops = enumerate_canonical_flops()
    indices = spread_indices(len(flops), jobs)
    payloads = [(i, flops[i], iterations, audit_samples, seed) for i in indices]

    results = []
    for workers in candidates:
        wall_started = time.perf_counter()
        task_results = []
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(_one_job, payload) for payload in payloads]
            for future in as_completed(futures):
                task_results.append(future.result())
        wall = time.perf_counter() - wall_started
        task_results.sort(key=lambda x: x["flop_index"])
        results.append(
            {
                "workers": workers,
                "wall_seconds": wall,
                "jobs": jobs,
                "jobs_per_minute": jobs * 60.0 / wall,
                "sum_task_seconds": sum(float(x["total_seconds"]) for x in task_results),
                "sum_solve_seconds": sum(float(x["solve_seconds"]) for x in task_results),
                "sum_audit_seconds": sum(float(x["audit_seconds"]) for x in task_results),
            }
        )

    winner = min(results, key=lambda x: (float(x["wall_seconds"]), int(x["workers"])))
    return {
        "benchmark_version": BENCHMARK_VERSION,
        "purpose": "finite CPU-parallelism calibration only; no strategic gate",
        "logical_processors": logical,
        "num_players": 8,
        "flop_selection": "64 evenly spread canonical flops by default",
        "jobs": jobs,
        "iterations_per_job": iterations,
        "audit_samples_per_job": audit_samples,
        "seed": seed,
        "candidates": list(candidates),
        "results": results,
        "selected_workers": int(winner["workers"]),
        "selection_rule": "minimum one-pass wall_seconds; tie -> lower workers",
    }


def _parse_candidates(text: str, logical: int) -> tuple[int, ...]:
    if text.strip():
        values = tuple(sorted({int(x.strip()) for x in text.split(",") if x.strip()}))
    else:
        values = default_worker_candidates(logical)
    return values


def main() -> None:
    logical = os.cpu_count() or 1
    ap = argparse.ArgumentParser(description="Finite DeepPot Ryzen worker-count benchmark")
    ap.add_argument("--candidates", default="", help="comma list; default derives 3 levels from logical CPU count")
    ap.add_argument("--jobs", type=int, default=64)
    ap.add_argument("--iterations", type=int, default=3000)
    ap.add_argument("--audit-samples", type=int, default=3000)
    ap.add_argument("--seed", type=int, default=123)
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--out-selected", required=True)
    args = ap.parse_args()

    result = run_worker_benchmark(
        candidates=_parse_candidates(args.candidates, logical),
        jobs=args.jobs,
        iterations=args.iterations,
        audit_samples=args.audit_samples,
        seed=args.seed,
    )
    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    out_selected = Path(args.out_selected)
    out_selected.parent.mkdir(parents=True, exist_ok=True)
    out_selected.write_text(str(result["selected_workers"]) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
