from __future__ import annotations

import argparse
import cProfile
import io
import json
import pstats
import time
from pathlib import Path

from deeppot.cards import Card, enumerate_canonical_flops
from deeppot.solver import ChanceSampledCFR
from deeppot.state_space import decision_scenario_count


def _cards_from_key(key):
    return tuple(Card(rank, suit) for rank, suit in key)


def _run_case(n: int, flop_index: int, iterations: int, warmup: int) -> dict:
    flops = list(enumerate_canonical_flops())
    flop_key = flops[flop_index]
    flop = _cards_from_key(flop_key)

    if warmup:
        w = ChanceSampledCFR(
            num_players=n,
            flop=flop,
            rake_pct=0.02,
            rake_cap=None,
            seed=999_000 + n,
            cfr_plus=True,
            linear_average=True,
        )
        w.solve(warmup)

    solver = ChanceSampledCFR(
        num_players=n,
        flop=flop,
        rake_pct=0.02,
        rake_cap=None,
        seed=123,
        cfr_plus=True,
        linear_average=True,
    )
    started = time.perf_counter()
    result = solver.solve(iterations)
    elapsed = time.perf_counter() - started
    scenarios = decision_scenario_count(n)
    cfr_nodes = iterations * scenarios
    return {
        "n": n,
        "flop_index": flop_index,
        "flop_key": [list(x) for x in flop_key],
        "hole_state_count": result.hole_state_count,
        "public_scenarios": scenarios,
        "iterations": iterations,
        "seconds": elapsed,
        "iterations_per_second": iterations / elapsed,
        "cfr_decision_nodes": cfr_nodes,
        "cfr_decision_nodes_per_second": cfr_nodes / elapsed,
        "seven_card_evaluations": iterations * n,
        "seven_card_evaluations_per_second": iterations * n / elapsed,
        "materialized_nodes": len(result.nodes),
    }


def _profile_n8(flop_index: int, iterations: int) -> str:
    flops = list(enumerate_canonical_flops())
    flop = _cards_from_key(flops[flop_index])
    solver = ChanceSampledCFR(
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
    stats = pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats("cumtime")
    stats.print_stats(35)
    return stream.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark/profile the current exact DeepPot Python CFR hot path on the Ryzen.")
    parser.add_argument("--iterations", type=int, default=2000)
    parser.add_argument("--warmup", type=int, default=100)
    parser.add_argument("--flop-index", type=int, default=877)
    parser.add_argument("--profile-iterations", type=int, default=150)
    parser.add_argument("--out", default="runs/kernel_benchmark_baseline")
    args = parser.parse_args()

    if args.iterations <= 0 or args.warmup < 0 or args.profile_iterations <= 0:
        raise SystemExit("iteration counts must be positive (warmup may be zero)")
    flops = list(enumerate_canonical_flops())
    if not 0 <= args.flop_index < len(flops):
        raise SystemExit(f"flop-index must be in 0..{len(flops)-1}")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    print("DEEPPOT CURRENT-KERNEL BASELINE")
    print(f"  representative canonical flop index: {args.flop_index}")
    print(f"  timed iterations per N: {args.iterations:,}")
    print(f"  warmup iterations per N: {args.warmup:,}")
    print()

    cases = []
    for n in (2, 5, 8):
        row = _run_case(n, args.flop_index, args.iterations, args.warmup)
        cases.append(row)
        print(
            f"N={n} scenarios={row['public_scenarios']:3d} "
            f"wall={row['seconds']:.3f}s "
            f"iter/s={row['iterations_per_second']:.2f} "
            f"decision-nodes/s={row['cfr_decision_nodes_per_second']:,.0f} "
            f"7card-evals/s={row['seven_card_evaluations_per_second']:,.0f}"
        )

    profile_text = _profile_n8(args.flop_index, args.profile_iterations)
    (out / "profile_N8.txt").write_text(profile_text, encoding="utf-8")

    payload = {
        "format": "DeepPot current Python kernel baseline",
        "method": "exact CFR+ / linear average / 2% uncapped / seed 123",
        "representative_flop_index": args.flop_index,
        "timed_iterations": args.iterations,
        "warmup_iterations": args.warmup,
        "profile_iterations_n8": args.profile_iterations,
        "cases": cases,
    }
    (out / "baseline.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    print()
    print(f"JSON: {out / 'baseline.json'}")
    print(f"N8 profile: {out / 'profile_N8.txt'}")
    print("\n--- N8 cProfile top cumulative functions ---")
    print(profile_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
