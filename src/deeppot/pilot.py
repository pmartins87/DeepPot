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

PILOT_VERSION = "2026-09-07.4"


def _source_hash() -> str:
    h = hashlib.sha256()
    root = Path(__file__).resolve().parent
    for name in (
        "cards.py",
        "economics.py",
        "equity.py",
        "evaluator.py",
        "exact_index.py",
        "game.py",
        "hu_response.py",
        "scenarios.py",
        "solver.py",
        "state_space.py",
        "validation.py",
        "pilot.py",
    ):
        h.update(name.encode())
        h.update((root / name).read_bytes())
    return h.hexdigest()


def _parse_flop(text: str) -> tuple[Card, Card, Card]:
    toks = text.replace(",", " ").split()
    if len(toks) != 3:
        raise ValueError("--flop must contain exactly 3 cards, e.g. 'Ah 7d 2c'")
    cards = tuple(Card.parse(x) for x in toks)
    return cards  # type: ignore[return-value]


def _solve_one(args: tuple[int, int, tuple[Card, Card, Card], int, float, float | None]) -> SolveResult:
    num_players, seed, flop, iterations, rake_pct, rake_cap = args
    return ChanceSampledCFR(
        num_players=num_players,
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
        w.writerow([
            "infoset_key",
            "public_scenario_id",
            "exact_hole_state_id",
            "p_fold",
            "p_stay",
            "visits",
        ])
        for key in sorted(result.nodes):
            node = result.nodes[key]
            public_id, hole_id = result.decode_infoset_key(key)
            p_fold, p_stay = node.average_strategy()
            w.writerow([
                key,
                public_id,
                hole_id,
                f"{p_fold:.12g}",
                f"{p_stay:.12g}",
                node.visits,
            ])


def _write_consensus_policy(path: Path, results: list[SolveResult]) -> int:
    """Average seed policies without merging any exact information sets."""

    if not results:
        raise ValueError("at least one solve result is required")
    hole_count = results[0].hole_state_count
    flop_key = results[0].flop_key
    for result in results[1:]:
        if result.hole_state_count != hole_count or result.flop_key != flop_key:
            raise ValueError("cannot average policies from different exact flop spaces")

    policies = [result.average_policy() for result in results]
    key_sets = [set(policy) for policy in policies]
    shared = set.intersection(*key_sets)
    union = set.union(*key_sets)
    if shared != union:
        raise ValueError("consensus policy requires identical infoset coverage across seeds")

    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "infoset_key",
            "public_scenario_id",
            "exact_hole_state_id",
            "p_fold",
            "p_stay",
            "visits",
        ])
        for key in sorted(shared):
            p_stay = sum(policy[key][1] for policy in policies) / len(policies)
            p_fold = 1.0 - p_stay
            public_id, hole_id = divmod(key, hole_count)
            visits = sum(result.nodes[key].visits for result in results)
            w.writerow([
                key,
                public_id,
                hole_id,
                f"{p_fold:.12g}",
                f"{p_stay:.12g}",
                visits,
            ])
    return len(shared)


def main() -> None:
    ap = argparse.ArgumentParser(description="DeepPot fixed-flop exact-state cross-seed pilot for N=2..8")
    ap.add_argument("--players", type=int, default=2)
    ap.add_argument("--flop", default="Ah 7d 2c")
    ap.add_argument("--iterations", type=int, default=10000)
    ap.add_argument("--seeds", default="1,2,3")
    ap.add_argument("--rake-pct", type=float, default=0.02)
    ap.add_argument("--rake-cap", type=float, default=None)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--out-dir", default="")
    args = ap.parse_args()

    if not 2 <= args.players <= 8:
        raise SystemExit("--players must be between 2 and 8")
    flop = _parse_flop(args.flop)
    seeds = [int(x.strip()) for x in args.seeds.split(",") if x.strip()]
    if not seeds:
        raise SystemExit("No seeds supplied")
    out = Path(args.out_dir) if args.out_dir else Path("runs") / f"n{args.players}_pilot_{int(time.time())}"
    out.mkdir(parents=True, exist_ok=True)

    manifest = {
        "pilot_version": PILOT_VERSION,
        "source_sha256": _source_hash(),
        "stage": "started",
        "generated_at_unix": time.time(),
        "python_version": sys.version,
        "platform": platform.platform(),
        "num_players": args.players,
        "flop": [str(c) for c in flop],
        "iterations": args.iterations,
        "seeds": seeds,
        "rake_pct": args.rake_pct,
        "rake_cap": args.rake_cap,
        "workers": args.workers,
        "solver": "exact_state_chance_sampled_cfr_plus_linear_average",
        "strategic_card_abstraction": "none",
        "exact_symmetry_reduction": "global_suit_isomorphism_only",
    }
    (out / "RUN_MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    jobs = [(args.players, s, flop, args.iterations, args.rake_pct, args.rake_cap) for s in seeds]
    started = time.perf_counter()
    if args.workers > 1:
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            results = list(ex.map(_solve_one, jobs))
    else:
        results = [_solve_one(j) for j in jobs]
    elapsed = time.perf_counter() - started

    seed_policies = {}
    visit_summary = {}
    for result in results:
        _write_policy(out / f"policy_seed_{result.seed}.csv", result)
        seed_policies[result.seed] = result.average_policy()
        visits = sorted(node.visits for node in result.nodes.values())
        visit_summary[str(result.seed)] = {
            "infosets": len(visits),
            "exact_hole_states_on_flop": result.hole_state_count,
            "min_visits": visits[0] if visits else 0,
            "median_visits": visits[len(visits)//2] if visits else 0,
            "max_visits": visits[-1] if visits else 0,
        }

    consensus_infosets = _write_consensus_policy(out / "policy_consensus.csv", results)
    pairwise, consensus = build_consensus(seed_policies)
    total_iterations = args.iterations * len(seeds)
    summary = {
        "num_players": args.players,
        "pairwise": [audit_to_dict(x) for x in pairwise],
        "consensus": audit_to_dict(consensus),
        "consensus_policy_infosets": consensus_infosets,
        "visits": visit_summary,
        "performance": {
            "wall_seconds": elapsed,
            "total_seed_iterations": total_iterations,
            "seed_iterations_per_second": total_iterations / elapsed if elapsed > 0 else 0.0,
        },
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    manifest["stage"] = "completed"
    manifest["completed_at_unix"] = time.time()
    manifest["wall_seconds"] = elapsed
    manifest["outputs"] = [
        "summary.json",
        "policy_consensus.csv",
        *[f"policy_seed_{s}.csv" for s in seeds],
    ]
    (out / "RUN_MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
