from __future__ import annotations

import argparse
import json
import math
import random
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

from deeppot import continuous_training_fast_v2 as ct
from deeppot.continuous_runner_fast_v2 import production_source_sha256
from deeppot.multiway_response import MultiwayResponseValidator, RunningStats
from deeppot.state_space import decision_scenario_count


POPULATION_FAMILIES = (
    "cfr_mixed",
    "cfr_greedy",
    "tight",
    "loose",
    "sharpened",
    "flattened",
    "early_tight_late_loose",
    "early_loose_late_tight",
)

HERO_POLICIES = (
    "mixed",
    "greedy",
    "hybrid60",
    "hybrid70",
    "hybrid80",
    "hybrid90",
)


def _clamp_prob(p: float) -> float:
    return min(1.0 - 1e-9, max(1e-9, float(p)))


def _logit(p: float) -> float:
    q = _clamp_prob(p)
    return math.log(q / (1.0 - q))


def _sigmoid(x: float) -> float:
    if x >= 0.0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def _population_pstay(name: str, p: float, actor: int, n: int) -> float:
    p = _clamp_prob(p)
    if name == "cfr_mixed":
        return p
    if name == "cfr_greedy":
        return 1.0 if p >= 0.5 else 0.0
    x = _logit(p)
    if name == "tight":
        return _sigmoid(x - 0.60)
    if name == "loose":
        return _sigmoid(x + 0.60)
    if name == "sharpened":
        return _sigmoid(1.75 * x)
    if name == "flattened":
        return _sigmoid(0.60 * x)
    pos = 0.0 if n <= 1 else actor / float(n - 1)
    if name == "early_tight_late_loose":
        return _sigmoid(x + (-0.60 + 1.20 * pos))
    if name == "early_loose_late_tight":
        return _sigmoid(x + (0.60 - 1.20 * pos))
    raise ValueError(f"unknown population family: {name}")


def _hero_pstay(name: str, p: float) -> float:
    if name == "mixed":
        return p
    greedy = 1.0 if p >= 0.5 else 0.0
    if name == "greedy":
        return greedy
    if name.startswith("hybrid"):
        threshold = int(name.removeprefix("hybrid")) / 100.0
        majority = max(p, 1.0 - p)
        return greedy if majority >= threshold else p
    raise ValueError(f"unknown hero policy: {name}")


def _choose_tasks(tasks_per_n: int, seed: int) -> list[ct.Task]:
    all_tasks = ct._all_tasks()
    out: list[ct.Task] = []
    for n in range(2, 9):
        candidates = [t for t in all_tasks if t.n == n]
        rng = random.Random(seed + n * 100003)
        picked = candidates if tasks_per_n >= len(candidates) else rng.sample(candidates, tasks_per_n)
        picked.sort(key=lambda t: t.flop_index)
        out.extend(picked)
    return out


def _make_policy(
    base_policy: dict[int, tuple[float, float]],
    *,
    family: str,
    actor_by_public: tuple[int, ...],
    hole_state_count: int,
    n: int,
) -> dict[int, tuple[float, float]]:
    out: dict[int, tuple[float, float]] = {}
    for key, (_pf, ps) in base_policy.items():
        public_id, _hole_id = divmod(key, hole_state_count)
        actor = actor_by_public[public_id]
        q = _population_pstay(family, ps, actor, n)
        out[key] = (1.0 - q, q)
    return out


def _sample_deals(validator: MultiwayResponseValidator, samples: int, seed: int):
    rng = random.Random(seed)
    need = 2 * validator.num_players + 2
    for _ in range(samples):
        cards = rng.sample(validator._deck, need)
        holes = []
        pos = 0
        for _p in range(validator.num_players):
            holes.append(tuple(sorted((cards[pos], cards[pos + 1]))))
            pos += 2
        yield tuple(holes), cards[pos], cards[pos + 1]


def _task_report(
    *,
    root: Path,
    task: ct.Task,
    source_sha: str,
    samples: int,
    rake_pct: float,
    cashback_per_contribution: float,
    seed: int,
) -> dict:
    config = ct.ContinuousConfig(seed=123, rake_pct=rake_pct, rake_cap=None, cfr_plus=True, linear_average=True)
    solver, iterations = ct.load_state(root=root, task=task, config=config, source_sha256=source_sha)
    expected = decision_scenario_count(task.n) * solver.hole_state_count
    base_policy: dict[int, tuple[float, float]] = {}
    for key in range(expected):
        node = solver.nodes.get(key)
        base_policy[key] = (0.5, 0.5) if node is None else node.average_strategy()

    base_validator = MultiwayResponseValidator(
        num_players=task.n,
        flop=solver.flop,
        policy=base_policy,
        rake_pct=rake_pct,
        rake_cap=None,
        seed=seed,
    )
    deals = list(_sample_deals(base_validator, samples, seed + 17))
    rows: list[dict] = []

    for family_idx, family in enumerate(POPULATION_FAMILIES):
        pop_policy = _make_policy(
            base_policy,
            family=family,
            actor_by_public=base_validator.actor_by_public,
            hole_state_count=solver.hole_state_count,
            n=task.n,
        )
        validator = MultiwayResponseValidator(
            num_players=task.n,
            flop=solver.flop,
            policy=pop_policy,
            rake_pct=rake_pct,
            rake_cap=None,
            seed=seed + family_idx * 1009,
        )
        node_count = len(validator.nodes)
        n = task.n
        values = [0.0] * (node_count * n)
        p_stay_by_node = [0.0] * node_count
        reach = [0.0] * node_count
        per_policy = {name: RunningStats() for name in HERO_POLICIES}
        per_actor = {(name, actor): RunningStats() for name in HERO_POLICIES for actor in range(n)}
        live_gap_shift = n * cashback_per_contribution

        for holes, turn, river in deals:
            hole_ids, _ = validator._fill_profile(
                holes=holes,
                turn=turn,
                river=river,
                values=values,
                p_stay_by_node=p_stay_by_node,
            )
            validator._fill_reach(p_stay_by_node, reach)
            delta_by_policy_actor = {name: [0.0] * n for name in HERO_POLICIES}

            for idx, node in enumerate(validator.nodes):
                if node.terminal:
                    continue
                assert node.actor is not None and node.public_id is not None
                assert node.fold_child is not None and node.stay_child is not None
                actor = node.actor
                r = reach[idx]
                if r <= 0.0:
                    continue
                key = node.public_id * solver.hole_state_count + hole_ids[actor]
                p_mixed = base_policy[key][1]
                gap = values[node.stay_child * n + actor] - values[node.fold_child * n + actor]
                live_gap = gap + live_gap_shift
                for hero_name in HERO_POLICIES:
                    p_hero = _hero_pstay(hero_name, p_mixed)
                    delta_by_policy_actor[hero_name][actor] += r * (p_hero - p_mixed) * live_gap

            for hero_name in HERO_POLICIES:
                actor_deltas = delta_by_policy_actor[hero_name]
                for actor, delta in enumerate(actor_deltas):
                    per_actor[(hero_name, actor)].add(delta)
                per_policy[hero_name].add(sum(actor_deltas) / n)

        for hero_name in HERO_POLICIES:
            est = per_policy[hero_name].estimate()
            rows.append(
                {
                    "n": task.n,
                    "flop_index": task.flop_index,
                    "iterations_completed": iterations,
                    "population": family,
                    "hero_policy": hero_name,
                    "samples": est.samples,
                    "delta_ev_vs_mixed": est.mean,
                    "std_error": est.std_error,
                    "ci95_low": est.ci95_low,
                    "ci95_high": est.ci95_high,
                    "actor_deltas": [
                        {"actor": actor, **asdict(per_actor[(hero_name, actor)].estimate())}
                        for actor in range(n)
                    ],
                }
            )
    return {"n": task.n, "flop_index": task.flop_index, "iterations_completed": iterations, "rows": rows}


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _aggregate(rows: list[dict]) -> dict:
    by_policy: dict[str, dict] = {}
    for hero in HERO_POLICIES:
        r = [x for x in rows if x["hero_policy"] == hero]
        by_pop = {
            pop: _mean([float(x["delta_ev_vs_mixed"]) for x in r if x["population"] == pop])
            for pop in POPULATION_FAMILIES
        }
        by_n = {
            str(n): _mean([float(x["delta_ev_vs_mixed"]) for x in r if int(x["n"]) == n])
            for n in range(2, 9)
        }
        vals = [float(x["delta_ev_vs_mixed"]) for x in r]
        by_policy[hero] = {
            "mean_delta_ev_vs_mixed": _mean(vals),
            "worst_population_mean": min(by_pop.values()) if by_pop else 0.0,
            "worst_n_mean": min(by_n.values()) if by_n else 0.0,
            "positive_task_population_cells_pct": 100.0 * sum(v > 0.0 for v in vals) / max(1, len(vals)),
            "significant_positive_cells_pct": 100.0 * sum(float(x["ci95_low"]) > 0.0 for x in r) / max(1, len(r)),
            "significant_negative_cells_pct": 100.0 * sum(float(x["ci95_high"]) < 0.0 for x in r) / max(1, len(r)),
            "by_population": by_pop,
            "by_n": by_n,
        }

    envs: dict[tuple[int, int, str], dict[str, float]] = defaultdict(dict)
    for x in rows:
        env = (int(x["n"]), int(x["flop_index"]), str(x["population"]))
        envs[env][str(x["hero_policy"])] = float(x["delta_ev_vs_mixed"])
    for hero in HERO_POLICIES:
        regrets = []
        for scores in envs.values():
            if hero not in scores:
                continue
            regrets.append(max(scores.values()) - scores[hero])
        by_policy[hero]["mean_candidate_regret"] = _mean(regrets)
        by_policy[hero]["max_candidate_regret"] = max(regrets) if regrets else 0.0

    return {"by_policy": by_policy, "environment_count": len(envs)}


def main() -> None:
    ap = argparse.ArgumentParser(description="SEL3500 robustness gate: mixed vs greedy vs hybrid against fixed population families")
    ap.add_argument("--training-root", default=r"C:\DeepPot\runs\continuous_master_fast_v2")
    ap.add_argument("--tasks-per-n", type=int, default=4)
    ap.add_argument("--samples-per-task", type=int, default=1500)
    ap.add_argument("--seed", type=int, default=9143500)
    ap.add_argument("--rake", type=float, default=0.02)
    ap.add_argument("--cashback-per-contribution", type=float, default=0.007)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    root = Path(args.training_root).resolve()
    source_sha = production_source_sha256()
    tasks = _choose_tasks(args.tasks_per_n, args.seed)
    out_dir = Path(args.out) if args.out else root / "analysis" / "base_policy_robustness_SEL3500"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("DeepPot SEL3500 base-policy robustness gate")
    print("  question: mixed vs greedy vs hybrid against fixed, non-adaptive population families")
    print(f"  tasks: {len(tasks)} ({args.tasks_per_n} canonical flops per N=2..8)")
    print(f"  chance deals/task: {args.samples_per_task}")
    print(f"  hero policies: {', '.join(HERO_POLICIES)}")
    print(f"  population families: {', '.join(POPULATION_FAMILIES)}")
    print(f"  live economics in comparisons: gross rake={100*args.rake:.2f}% + observed Hero cashback={100*args.cashback_per_contribution:.3f}% of contribution")
    print("  common random deals are reused across population families within each task")
    print("  all populations are fixed/non-adaptive; no opponent-specific exploitation is assumed")
    print("  read-only: CFR state, RNG, snapshots, DLL and formula are NOT modified")

    reports = []
    rows: list[dict] = []
    for i, task in enumerate(tasks, 1):
        rep = _task_report(
            root=root,
            task=task,
            source_sha=source_sha,
            samples=args.samples_per_task,
            rake_pct=args.rake,
            cashback_per_contribution=args.cashback_per_contribution,
            seed=args.seed + i * 1000003,
        )
        reports.append(rep)
        rows.extend(rep["rows"])
        greedy_rows = [r for r in rep["rows"] if r["hero_policy"] == "greedy"]
        gmean = _mean([float(r["delta_ev_vs_mixed"]) for r in greedy_rows])
        print(f"  [{i:02d}/{len(tasks):02d}] N={task.n} flop={task.flop_index:04d} greedy mean delta vs mixed={gmean:+.5f} ante", flush=True)

    summary = _aggregate(rows)
    payload = {
        "format": "DeepPot SEL3500 fixed-population base-policy robustness gate",
        "training_root": str(root),
        "source_sha256": source_sha,
        "seed": args.seed,
        "tasks_per_n": args.tasks_per_n,
        "samples_per_task": args.samples_per_task,
        "rake_pct": args.rake,
        "cashback_per_contribution": args.cashback_per_contribution,
        "hero_policies": list(HERO_POLICIES),
        "population_families": list(POPULATION_FAMILIES),
        "reports": reports,
        "summary": summary,
        "interpretation_guardrail": "EV deltas are against fixed synthetic population families derived from SEL3500, not claims about the actual KKPoker population.",
    }
    out_json = out_dir / "base_policy_robustness.json"
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print("\nPolicy summary (EV delta vs mixed, ante/hand; equal weight across sampled task/population cells):")
    for hero in HERO_POLICIES:
        s = summary["by_policy"][hero]
        print(
            f"  {hero:9s} mean={s['mean_delta_ev_vs_mixed']:+.5f} "
            f"worst_pop={s['worst_population_mean']:+.5f} worst_N={s['worst_n_mean']:+.5f} "
            f"cells>0={s['positive_task_population_cells_pct']:.1f}% "
            f"sig+={s['significant_positive_cells_pct']:.1f}% sig-={s['significant_negative_cells_pct']:.1f}% "
            f"mean_regret={s['mean_candidate_regret']:.5f} max_regret={s['max_candidate_regret']:.5f}"
        )

    print("\nBy population (mean delta EV vs mixed):")
    print("population".ljust(28) + " ".join(h.rjust(10) for h in HERO_POLICIES))
    for pop in POPULATION_FAMILIES:
        line = pop.ljust(28)
        for hero in HERO_POLICIES:
            line += f" {summary['by_policy'][hero]['by_population'][pop]:+10.5f}"
        print(line)

    print("\nBy N (mean delta EV vs mixed across population families/tasks):")
    print("N".ljust(4) + " ".join(h.rjust(10) for h in HERO_POLICIES))
    for n in range(2, 9):
        line = str(n).ljust(4)
        for hero in HERO_POLICIES:
            line += f" {summary['by_policy'][hero]['by_n'][str(n)]:+10.5f}"
        print(line)

    print(f"\nJSON: {out_json}")


if __name__ == "__main__":
    main()
