from __future__ import annotations

import argparse
import csv
import json
import math
import random
from pathlib import Path

from deeppot import continuous_training_fast_v2 as ct
from deeppot.cards import full_deck
from deeppot.continuous_runner_fast_v2 import production_source_sha256
from deeppot.multiway_response import MultiwayResponseValidator


def _load_candidates(path: Path, top_per_n: int, n_min: int, n_max: int) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    out: list[dict] = []
    for n in range(n_min, n_max + 1):
        rr = [r for r in rows if int(r["n"]) == n]
        rr.sort(key=lambda r: float(r["changed_pct"]), reverse=True)
        out.extend(rr[:top_per_n])
    return out


def _mean_ci95(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, float("inf")
    mean = sum(values) / len(values)
    if len(values) <= 1:
        return mean, float("inf")
    var = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
    se = math.sqrt(var / len(values))
    return mean, 1.959963984540054 * se


def _sample_keys(rng: random.Random, population: list[int], k: int) -> list[int]:
    if len(population) <= k:
        return list(population)
    return rng.sample(population, k)


def _conditional_gap_samples(
    *,
    validator: MultiwayResponseValidator,
    public_id: int,
    hole_state_id: int,
    samples: int,
    rng: random.Random,
    representative_hole: dict[int, tuple],
    node_by_public: dict[int, int],
) -> list[float]:
    node_idx = node_by_public[public_id]
    node = validator.nodes[node_idx]
    assert node.actor is not None
    assert node.fold_child is not None and node.stay_child is not None
    actor = node.actor
    hero_hole = representative_hole[hole_state_id]

    available = [c for c in validator._deck if c not in hero_hole]
    need = 2 * (validator.num_players - 1) + 2
    n = validator.num_players
    values = [0.0] * (len(validator.nodes) * n)
    p_stay_by_node = [0.0] * len(validator.nodes)
    gaps: list[float] = []

    for _ in range(samples):
        picked = rng.sample(available, need)
        holes: list[tuple] = [tuple() for _ in range(n)]
        holes[actor] = hero_hole
        pos = 0
        for p in range(n):
            if p == actor:
                continue
            holes[p] = tuple(sorted((picked[pos], picked[pos + 1])))
            pos += 2
        turn = picked[pos]
        river = picked[pos + 1]
        validator._fill_profile(
            holes=tuple(holes),
            turn=turn,
            river=river,
            values=values,
            p_stay_by_node=p_stay_by_node,
        )
        gap = values[node.stay_child * n + actor] - values[node.fold_child * n + actor]
        gaps.append(gap)
    return gaps


def _task_report(
    *,
    root: Path,
    task: ct.Task,
    source_sha: str,
    samples_per_state: int,
    random_fold_states: int,
    marginal_fold_states: int,
    marginal_low: float,
    pvi_factors: list[float],
    nominal_rb: float,
    rake_pct: float,
    seed: int,
) -> dict:
    config = ct.ContinuousConfig(
        seed=123,
        rake_pct=rake_pct,
        rake_cap=None,
        cfr_plus=True,
        linear_average=True,
    )
    solver, iterations = ct.load_state(root=root, task=task, config=config, source_sha256=source_sha)
    expected = task.n and (len(solver.nodes) if False else 0)
    scenarios = __import__("deeppot.state_space", fromlist=["decision_scenario_count"]).decision_scenario_count(task.n)
    expected = scenarios * solver.hole_state_count

    policy: dict[int, tuple[float, float]] = {}
    all_fold: list[int] = []
    marginal_fold: list[int] = []
    for key in range(expected):
        node = solver.nodes.get(key)
        avg = (0.5, 0.5) if node is None else node.average_strategy()
        policy[key] = avg
        p_stay = avg[1]
        if p_stay < 0.5:
            all_fold.append(key)
            if p_stay >= marginal_low:
                marginal_fold.append(key)

    validator = MultiwayResponseValidator(
        num_players=task.n,
        flop=solver.flop,
        policy=policy,
        rake_pct=rake_pct,
        rake_cap=None,
        seed=seed,
    )

    representative_hole: dict[int, tuple] = {}
    for raw_hole, sid in validator._raw_hole_to_state_id.items():
        representative_hole.setdefault(sid, raw_hole)
    if len(representative_hole) != validator.hole_state_count:
        raise RuntimeError("failed to build representative raw hole for every exact hole state")

    node_by_public: dict[int, int] = {}
    for idx, node in enumerate(validator.nodes):
        if node.public_id is not None:
            node_by_public[node.public_id] = idx

    rng = random.Random(seed)
    sampled_marginal = _sample_keys(rng, marginal_fold, marginal_fold_states)
    marginal_set = set(sampled_marginal)
    broad_pool = [k for k in all_fold if k not in marginal_set]
    sampled_random = _sample_keys(rng, broad_pool, random_fold_states)

    rows: list[dict] = []
    for stratum, keys in (("marginal_fold", sampled_marginal), ("random_fold", sampled_random)):
        for key in keys:
            public_id, hole_state_id = divmod(key, solver.hole_state_count)
            p_stay = policy[key][1]
            gaps = _conditional_gap_samples(
                validator=validator,
                public_id=public_id,
                hole_state_id=hole_state_id,
                samples=samples_per_state,
                rng=rng,
                representative_hole=representative_hole,
                node_by_public=node_by_public,
            )
            mean_gap, ci95 = _mean_ci95(gaps)
            record = {
                "key": key,
                "public_id": public_id,
                "hole_state_id": hole_state_id,
                "stratum": stratum,
                "solver_p_stay": p_stay,
                "baseline_gap": mean_gap,
                "ci95": ci95,
                "factors": {},
            }
            for factor in pvi_factors:
                cashback = rake_pct * nominal_rb * factor
                shift = task.n * cashback
                rebate_gap = mean_gap + shift
                record["factors"][f"{factor:.4f}"] = {
                    "gap_shift": shift,
                    "rebate_gap": rebate_gap,
                    "fold_to_stay_flip": int(mean_gap <= 0.0 < rebate_gap),
                    "confident_reversal": int(
                        math.isfinite(ci95)
                        and mean_gap + ci95 < 0.0
                        and rebate_gap - ci95 > 0.0
                    ),
                    "rebate_ev_best_stay": int(rebate_gap > 0.0),
                }
            rows.append(record)

    aggregate: dict[str, dict] = {}
    for factor in pvi_factors:
        fk = f"{factor:.4f}"
        agg = {}
        for stratum in ("marginal_fold", "random_fold"):
            rr = [r for r in rows if r["stratum"] == stratum]
            flips = sum(r["factors"][fk]["fold_to_stay_flip"] for r in rr)
            conf = sum(r["factors"][fk]["confident_reversal"] for r in rr)
            agg[stratum] = {
                "sampled_states": len(rr),
                "fold_to_stay_flips": flips,
                "flip_pct": 100.0 * flips / max(1, len(rr)),
                "confident_reversals": conf,
            }
        aggregate[fk] = agg

    return {
        "n": task.n,
        "flop_index": task.flop_index,
        "iterations_completed": iterations,
        "expected_infosets": expected,
        "all_fold_states": len(all_fold),
        "marginal_fold_states_population": len(marginal_fold),
        "marginal_low": marginal_low,
        "samples_per_state": samples_per_state,
        "aggregate": aggregate,
        "rows": rows,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Conditional per-infoset DeepPot rakeback sensitivity audit")
    ap.add_argument("--training-root", default=r"C:\DeepPot\runs\continuous_master_fast_v2")
    ap.add_argument("--analysis-csv", default=r"C:\DeepPot\runs\continuous_master_fast_v2\analysis\V2_2000_to_V2_SEL2500\task_stability.csv")
    ap.add_argument("--top-per-n", type=int, default=3)
    ap.add_argument("--n-min", type=int, default=5)
    ap.add_argument("--n-max", type=int, default=8)
    ap.add_argument("--samples-per-state", type=int, default=150)
    ap.add_argument("--random-fold-states", type=int, default=75)
    ap.add_argument("--marginal-fold-states", type=int, default=75)
    ap.add_argument("--marginal-low", type=float, default=0.40)
    ap.add_argument("--seed", type=int, default=92741)
    ap.add_argument("--rake", type=float, default=0.02)
    ap.add_argument("--nominal-rb", type=float, default=0.50)
    ap.add_argument("--pvi-factors", default="0.60,0.70,0.80")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    root = Path(args.training_root).resolve()
    analysis_csv = Path(args.analysis_csv).resolve()
    if not analysis_csv.exists():
        raise RuntimeError(f"analysis CSV not found: {analysis_csv}")
    factors = [float(x.strip()) for x in args.pvi_factors.split(",") if x.strip()]
    candidates = _load_candidates(analysis_csv, args.top_per_n, args.n_min, args.n_max)
    task_map = {(t.n, t.flop_index): t for t in ct._all_tasks()}
    source_sha = production_source_sha256()

    out_dir = Path(args.out) if args.out else root / "analysis" / "rakeback_conditional_SEL2500"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("DeepPot conditional rakeback sensitivity audit")
    print(f"  tasks: {len(candidates)} | samples/state: {args.samples_per_state}")
    print(f"  per task: up to {args.marginal_fold_states} marginal FOLD + {args.random_fold_states} random FOLD states")
    print(f"  marginal band: p(STAY) in [{args.marginal_low:.2f}, 0.50)")
    print(f"  PVI factors: {', '.join(f'{x:.2f}' for x in factors)}")
    print("  read-only: persistent CFR state/RNG/snapshots are not modified")

    reports = []
    for i, row in enumerate(candidates, 1):
        n = int(row["n"])
        flop_index = int(row["flop_index"])
        task = task_map[(n, flop_index)]
        report = _task_report(
            root=root,
            task=task,
            source_sha=source_sha,
            samples_per_state=args.samples_per_state,
            random_fold_states=args.random_fold_states,
            marginal_fold_states=args.marginal_fold_states,
            marginal_low=args.marginal_low,
            pvi_factors=factors,
            nominal_rb=args.nominal_rb,
            rake_pct=args.rake,
            seed=args.seed + i * 100003,
        )
        report["prior_changed_pct"] = float(row["changed_pct"])
        reports.append(report)
        mid = f"{factors[len(factors)//2]:.4f}"
        a = report["aggregate"][mid]
        print(
            f"  [{i:02d}/{len(candidates):02d}] N={n} flop={flop_index:04d} "
            f"prior_change={float(row['changed_pct']):.4f}% "
            f"marginal flips={a['marginal_fold']['fold_to_stay_flips']}/{a['marginal_fold']['sampled_states']} "
            f"random flips={a['random_fold']['fold_to_stay_flips']}/{a['random_fold']['sampled_states']}",
            flush=True,
        )

    overall: dict[str, dict] = {}
    for factor in factors:
        fk = f"{factor:.4f}"
        overall[fk] = {}
        for stratum in ("marginal_fold", "random_fold"):
            denom = sum(r["aggregate"][fk][stratum]["sampled_states"] for r in reports)
            flips = sum(r["aggregate"][fk][stratum]["fold_to_stay_flips"] for r in reports)
            conf = sum(r["aggregate"][fk][stratum]["confident_reversals"] for r in reports)
            overall[fk][stratum] = {
                "sampled_states": denom,
                "fold_to_stay_flips": flips,
                "flip_pct": 100.0 * flips / max(1, denom),
                "confident_reversals": conf,
            }

    payload = {
        "format": "DeepPot conditional exact-infoset rakeback sensitivity audit",
        "method": "condition on sampled exact infoset; Monte Carlo opponent private cards+turn+river; integrate future actions with persisted CFR average policy",
        "analysis_csv": str(analysis_csv),
        "rake_pct": args.rake,
        "nominal_rakeback": args.nominal_rb,
        "pvi_factors": factors,
        "overall": overall,
        "tasks": reports,
    }
    out_json = out_dir / "rakeback_conditional.json"
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    print("\nOverall:")
    for factor in factors:
        fk = f"{factor:.4f}"
        cashback = 100.0 * args.rake * args.nominal_rb * factor
        print(f"  factor={factor:.2f} effectiveRB~{100.0*args.nominal_rb*factor:.1f}% cashback/contrib={cashback:.3f}%")
        for stratum in ("marginal_fold", "random_fold"):
            a = overall[fk][stratum]
            print(
                f"    {stratum}: flips={a['fold_to_stay_flips']}/{a['sampled_states']} "
                f"({a['flip_pct']:.3f}%) confident={a['confident_reversals']}"
            )
    print(f"\nJSON: {out_json}")


if __name__ == "__main__":
    main()
