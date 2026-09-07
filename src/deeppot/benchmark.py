from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import time
from pathlib import Path

from .cards import Card
from .solver import ChanceSampledCFR

BENCHMARK_VERSION = "2026-09-07.1"


def _parse_flop(text: str) -> tuple[Card, Card, Card]:
    toks = text.replace(",", " ").split()
    if len(toks) != 3:
        raise ValueError(f"invalid flop {text!r}; expected three cards")
    return tuple(Card.parse(x) for x in toks)  # type: ignore[return-value]


def _percentile(xs: list[int], q: float) -> float:
    if not xs:
        return 0.0
    ys = sorted(xs)
    if len(ys) == 1:
        return float(ys[0])
    pos = (len(ys) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(ys) - 1)
    frac = pos - lo
    return ys[lo] * (1.0 - frac) + ys[hi] * frac


def run_case(
    *,
    num_players: int,
    flop_text: str,
    iterations: int,
    seed: int,
    rake_pct: float,
    rake_cap: float | None,
) -> dict:
    flop = _parse_flop(flop_text)

    t0 = time.perf_counter()
    solver = ChanceSampledCFR(
        num_players=num_players,
        flop=flop,
        rake_pct=rake_pct,
        rake_cap=rake_cap,
        seed=seed,
        cfr_plus=True,
        linear_average=True,
    )
    init_seconds = time.perf_counter() - t0

    t1 = time.perf_counter()
    result = solver.solve(iterations)
    solve_seconds = time.perf_counter() - t1

    visits = [node.visits for node in result.nodes.values()]
    total_visits = sum(visits)
    return {
        "num_players": num_players,
        "flop": flop_text,
        "canonical_flop_key": result.flop_key,
        "exact_hole_states": result.hole_state_count,
        "flop_stabilizer_size": solver.exact_index.stabilizer_size,
        "iterations": iterations,
        "seed": seed,
        "rake_pct": rake_pct,
        "rake_cap": rake_cap,
        "init_seconds": init_seconds,
        "solve_seconds": solve_seconds,
        "iterations_per_second": iterations / solve_seconds if solve_seconds > 0 else 0.0,
        "infoset_visits_per_second": total_visits / solve_seconds if solve_seconds > 0 else 0.0,
        "infosets_touched": len(visits),
        "total_infoset_visits": total_visits,
        "min_visits": min(visits) if visits else 0,
        "median_visits": statistics.median(visits) if visits else 0.0,
        "p95_visits": _percentile(visits, 0.95),
        "max_visits": max(visits) if visits else 0,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="DeepPot abstraction-free exact-state throughput benchmark")
    ap.add_argument("--players", type=int, default=2)
    ap.add_argument(
        "--flops",
        default="Ah 7d 2c;Ah 7h 2c;Ah 7h 2h;Ah Ad 2c",
        help="semicolon-separated flop list",
    )
    ap.add_argument("--iterations", default="10000", help="comma-separated iteration counts")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--rake-pct", type=float, default=0.02)
    ap.add_argument("--rake-cap", type=float, default=None)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    flops = [x.strip() for x in args.flops.split(";") if x.strip()]
    iteration_counts = [int(x.strip()) for x in args.iterations.split(",") if x.strip()]
    if not flops or not iteration_counts:
        raise SystemExit("at least one flop and one iteration count are required")

    started = time.time()
    cases = []
    for flop in flops:
        for iterations in iteration_counts:
            case = run_case(
                num_players=args.players,
                flop_text=flop,
                iterations=iterations,
                seed=args.seed,
                rake_pct=args.rake_pct,
                rake_cap=args.rake_cap,
            )
            cases.append(case)
            print(json.dumps(case, indent=2))

    payload = {
        "benchmark_version": BENCHMARK_VERSION,
        "generated_at_unix": started,
        "python_version": sys.version,
        "platform": platform.platform(),
        "strategic_card_abstraction": "none",
        "exact_symmetry_reduction": "global_suit_isomorphism_only",
        "cases": cases,
    }
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
