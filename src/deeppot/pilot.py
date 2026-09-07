from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from .cards import Card
from .solver import ChanceSampledCFR, SolveResult
from .validation import audit_to_dict, build_consensus

PILOT_VERSION = "2026-09-07.1"


def _source_hash() -> str:
    h = hashlib.sha256()
    root = Path(__file__).resolve().parent
    for name in ("cards.py", "economics.py", "evaluator.py", "game.py", "scenarios.py", "solver.py", "validation.py", "pilot.py"):
        h.update(name.encode())
        h.update((root / name).read_bytes())
    return h.hexdigest()


def _parse_flop(text: str) -> tuple[Card, Card, Card]:
    toks = text.replace(",", " ").split()
    if len(toks) != 3:
        raise ValueError("--flop must contain exactly 3 cards, e.g. 'Ah 7d 2c'")
    cards = tuple(Card.parse(x) for x in toks)
    return cards  # type: ignore[return-value]


def _solve_one(args: tuple[int, tuple[Card, Card, Card], int, float, float | None]) -> SolveResult:
    seed, flop, iterations, rake_pct, rake_cap = args
    return ChanceSampledCFR(
        num_players=2,
        flop=flop,
        rake_pct=rake_pct,
        rake_cap=rake_cap,
        seed=seed,
        cfr_plus=True,
        linear_average=True,
    ).solve(iterations)


def _write_policy(path: Path, result: SolveResult) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["infoset", "p_fold", "p_stay", "visits"])
        for key in sorted(result.nodes):
            node = result.nodes[key]
            p_fold, p_stay = node.average_strategy()
            w.writerow([key, f"{p_fold:.12g}", f"{p_stay:.12g}", node.visits])


def main() -> None:
    ap = argparse.ArgumentParser(description="DeepPot HU fixed-flop cross-seed pilot")
    ap.add_argument("--flop", default="Ah 7d 2c")
    ap.add_argument("--iterations", type=int, default=10000)
    ap.add_argument("--seeds", default="1,2,3")
    ap.add_argument("--rake-pct", type=float, default=0.02)
    ap.add_argument("--rake-cap", type=float, default=None)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--out-dir", default="")
    args = ap.parse_args()

    flop = _parse_flop(args.flop)
    seeds = [int(x.strip()) for x in args.seeds.split(",") if x.strip()]
    if not seeds:
        raise SystemExit("No seeds supplied")
    out = Path(args.out_dir) if args.out_dir else Path("runs") / f"hu_pilot_{int(time.time())}"
    out.mkdir(parents=True, exist_ok=True)

    manifest = {
        "pilot_version": PILOT_VERSION,
        "source_sha256": _source_hash(),
        "stage": "started",
        "generated_at_unix": time.time(),
        "python_version": sys.version,
        "platform": platform.platform(),
        "flop": [str(c) for c in flop],
        "iterations": args.iterations,
        "seeds": seeds,
        "rake_pct": args.rake_pct,
        "rake_cap": args.rake_cap,
        "workers": args.workers,
        "solver": "chance_sampled_cfr_plus_linear_average",
    }
    (out / "RUN_MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    jobs = [(s, flop, args.iterations, args.rake_pct, args.rake_cap) for s in seeds]
    if args.workers > 1:
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            results = list(ex.map(_solve_one, jobs))
    else:
        results = [_solve_one(j) for j in jobs]

    seed_policies = {}
    visit_summary = {}
    for result in results:
        _write_policy(out / f"policy_seed_{result.seed}.csv", result)
        seed_policies[result.seed] = result.average_policy()
        visits = sorted(node.visits for node in result.nodes.values())
        visit_summary[str(result.seed)] = {
            "infosets": len(visits),
            "min_visits": visits[0] if visits else 0,
            "median_visits": visits[len(visits)//2] if visits else 0,
            "max_visits": visits[-1] if visits else 0,
        }

    pairwise, consensus = build_consensus(seed_policies)
    summary = {
        "pairwise": [audit_to_dict(x) for x in pairwise],
        "consensus": audit_to_dict(consensus),
        "visits": visit_summary,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    manifest["stage"] = "completed"
    manifest["completed_at_unix"] = time.time()
    manifest["outputs"] = ["summary.json", *[f"policy_seed_{s}.csv" for s in seeds]]
    (out / "RUN_MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
