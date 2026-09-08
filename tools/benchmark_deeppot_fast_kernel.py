from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from deeppot.cards import Card, enumerate_canonical_flops
from deeppot.fast_solver import FastChanceSampledCFR
from deeppot.solver import ChanceSampledCFR
from deeppot.state_space import decision_scenario_count


def _cards_from_key(key):
    return tuple(Card(rank, suit) for rank, suit in key)


def _run(cls, *, n: int, flop_index: int, iterations: int, warmup: int) -> dict:
    flops = list(enumerate_canonical_flops())
    flop_key = flops[flop_index]
    flop = _cards_from_key(flop_key)
    kwargs = dict(
        num_players=n,
        flop=flop,
        rake_pct=0.02,
        rake_cap=None,
        seed=123,
        cfr_plus=True,
        linear_average=True,
    )
    if warmup:
        w = cls(**kwargs)
        w.solve(warmup)
    solver = cls(**kwargs)
    started = time.perf_counter()
    solver.solve(iterations)
    seconds = time.perf_counter() - started
    scenarios = decision_scenario_count(n)
    return {
        "seconds": seconds,
        "iterations_per_second": iterations / seconds,
        "decision_nodes_per_second": iterations * scenarios / seconds,
    }


def main() -> int:
    p = argparse.ArgumentParser(description="A/B benchmark current vs exact fast DeepPot CFR kernel")
    p.add_argument("--iterations", type=int, default=5000)
    p.add_argument("--warmup", type=int, default=200)
    p.add_argument("--flop-index", type=int, default=877)
    p.add_argument("--out", default="runs/kernel_benchmark_fast")
    args = p.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = []

    print("DEEPPOT CFR KERNEL A/B")
    print(f"  flop index: {args.flop_index}")
    print(f"  iterations per implementation/N: {args.iterations:,}")
    print()

    for n in (2, 5, 8):
        ref = _run(ChanceSampledCFR, n=n, flop_index=args.flop_index, iterations=args.iterations, warmup=args.warmup)
        fast = _run(FastChanceSampledCFR, n=n, flop_index=args.flop_index, iterations=args.iterations, warmup=args.warmup)
        speedup = ref["seconds"] / fast["seconds"]
        row = {"n": n, "reference": ref, "fast": fast, "speedup": speedup}
        rows.append(row)
        print(
            f"N={n}  ref={ref['seconds']:.3f}s  fast={fast['seconds']:.3f}s  "
            f"speedup={speedup:.2f}x  fast_nodes/s={fast['decision_nodes_per_second']:,.0f}"
        )

    payload = {
        "format": "DeepPot exact CFR kernel A/B",
        "flop_index": args.flop_index,
        "iterations": args.iterations,
        "warmup": args.warmup,
        "rows": rows,
    }
    path = out / "fast_vs_reference.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nJSON: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
