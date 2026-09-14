from __future__ import annotations

import argparse
import csv
import json
import math
import random
from pathlib import Path

from deeppot import continuous_training_fast_v2 as ct
from deeppot.continuous_runner_fast_v2 import production_source_sha256
from deeppot.multiway_response import MultiwayResponseValidator
from deeppot.state_space import decision_scenario_count


def _load_candidates(path: Path, top_per_n: int, n_min: int, n_max: int) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    out: list[dict] = []
    for n in range(n_min, n_max + 1):
        rr = [r for r in rows if int(r["n"]) == n]
        rr.sort(key=lambda r: float(r["changed_pct"]), reverse=True)
        out.extend(rr[:top_per_n])
    return out


def _weighted_mean_ci95(samples: list[tuple[float, float]]) -> tuple[float, float, float]:
    sum_w = sum(w for _, w in samples)
    sum_w2 = sum(w * w for _, w in samples)
    if sum_w <= 0.0 or sum_w2 <= 0.0:
        return 0.0, float("inf"), 0.0
    mean = sum(x * w for x, w in samples) / sum_w
    second = sum(x * x * w for x, w in samples) / sum_w
    var = max(0.0, second - mean * mean)
    n_eff = (sum_w * sum_w) / sum_w2
    if n_eff <= 1.0:
        return mean, float("inf"), n_eff
    stderr = math.sqrt(var / n_eff)
    return mean, 1.959963984540054 * stderr, n_eff


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
) -> list[tuple[float, float]]:
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
    reach = [0.0] * len(validator.nodes)
    out: list[tuple[float, float]] = []

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
        validator._fill_reach(p_stay_by_node, reach)
        weight = reach[node_idx]
        if weight <= 0.0:
            continue
        gap = values[node.stay_child * n + actor] - values[node.fold_child * n + actor]
        out.append((gap, weight))
    return out


def _task_report(
    *,
    root: Path,
    task: ct.Task,
    source_sha: str,
    samples_per_state: int,
    marginal_states: int,
    random_states: int,
    marginal_low: float,
    marginal_high: float,
    min_effective_visits: float,
    rake_pct: float,
    nominal_rb: float,
    pvi_factors: list[float],
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
    expected = decision_scenario_count(task.n) * solver.hole_state_count

    policy: dict[int, tuple[float, float]] = {}
    marginal: list[int] = []
    broad: list[int] = []
    for key in range(expected):
        node = solver.nodes.get(key)
        avg = (0.5, 0.5) if node is None else node.average_strategy()
        policy[key] = avg
        p_stay = avg[1]
        if marginal_low <= p_stay <= marginal_high:
            marginal.append(key)
        else:
            broad.append(key)

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
    sampled_marginal = _sample_keys(rng, marginal, marginal_states)
    sampled_random = _sample_keys(rng, broad, random_states)

    rows: list[dict] = []
    for stratum, keys in (("marginal", sampled_marginal), ("random", sampled_random)):
        for key in keys:
            public_id, hole_state_id = divmod(key, solver.hole_state_count)
            p_stay = policy[key][1]
            samples = _conditional_gap_samples(
                validator=validator,
                public_id=public_id,
                hole_state_id=hole_state_id,
                samples=samples_per_state,
                rng=rng,
                representative_hole=representative_hole,
                node_by_public=node_by_public,
            )
            mean_gap, ci95, n_eff = _weighted_mean_ci95(samples)
            eligible = n_eff >= min_effective_visits and math.isfinite(ci95)
            solver_stay = p_stay >= 0.5
            baseline_best_stay = mean_gap > 0.0
            baseline_confident = eligible and abs(mean_gap) > ci95
            record = {
                "key": key,
                "public_id": public_id,
                "hole_state_id": hole_state_id,
                "stratum": stratum,
                "solver_p_stay": p_stay,
                "solver_greedy_action": "STAY" if solver_stay else "FOLD",
                "baseline_gap": mean_gap,
                "ci95": ci95,
                "effective_visits": n_eff,
                "eligible": int(eligible),
                "baseline_ev_best_action": "STAY" if baseline_best_stay else "FOLD",
                "baseline_confident": int(baseline_confident),
                "baseline_confident_mismatch": int(baseline_confident and solver_stay != baseline_best_stay),
                "factors": {},
            }
            for factor in pvi_factors:
                cashback = rake_pct * nominal_rb * factor
                shift = task.n * cashback
                gap = mean_gap + shift
                best_stay = gap > 0.0
                confident = eligible and abs(gap) > ci95
                record["factors"][f"{factor:.4f}"] = {
                    "cashback_per_contribution": cashback,
                    "gap_shift": shift,
                    "rebate_gap": gap,
                    "ev_best_action": "STAY" if best_stay else "FOLD",
                    "confident": int(confident),
                    "confident_mismatch": int(confident and solver_stay != best_stay),
                }
            rows.append(record)

    return {
        "n": task.n,
        "flop_index": task.flop_index,
        "iterations_completed": iterations,
        "expected_infosets": expected,
        "marginal_population": len(marginal),
        "broad_population": len(broad),
        "samples_per_state": samples_per_state,
        "rows": rows,
    }


def _summarize_rows(rows: list[dict], factor_key: str | None) -> dict:
    out: dict[str, dict] = {}
    for stratum in ("marginal", "random"):
        rr = [r for r in rows if r["stratum"] == stratum]
        eligible = [r for r in rr if r["eligible"]]
        if factor_key is None:
            confident = [r for r in eligible if r["baseline_confident"]]
            mismatches = [r for r in confident if r["baseline_confident_mismatch"]]
        else:
            confident = [r for r in eligible if r["factors"][factor_key]["confident"]]
            mismatches = [r for r in confident if r["factors"][factor_key]["confident_mismatch"]]
        out[stratum] = {
            "sampled_states": len(rr),
            "eligible_states": len(eligible),
            "confident_states": len(confident),
            "confident_mismatches": len(mismatches),
            "mismatch_pct_of_confident": 100.0 * len(mismatches) / max(1, len(confident)),
            "mismatch_pct_of_eligible": 100.0 * len(mismatches) / max(1, len(eligible)),
        }
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Conditional DeepKK-style EV/CI gate for DeepPot SEL3000")
    ap.add_argument("--training-root", default=r"C:\DeepPot\runs\continuous_master_fast_v2")
    ap.add_argument("--analysis-csv", default=r"C:\DeepPot\runs\continuous_master_fast_v2\analysis\V2_SEL2500_to_V2_SEL3000\task_stability.csv")
    ap.add_argument("--top-per-n", type=int, default=3)
    ap.add_argument("--n-min", type=int, default=5)
    ap.add_argument("--n-max", type=int, default=8)
    ap.add_argument("--samples-per-state", type=int, default=500)
    ap.add_argument("--marginal-states", type=int, default=50)
    ap.add_argument("--random-states", type=int, default=25)
    ap.add_argument("--marginal-low", type=float, default=0.40)
    ap.add_argument("--marginal-high", type=float, default=0.60)
    ap.add_argument("--min-effective-visits", type=float, default=25.0)
    ap.add_argument("--seed", type=int, default=77123)
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

    out_dir = Path(args.out) if args.out else root / "analysis" / "deepkk_final_gate_SEL3000"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("DeepPot conditional DeepKK-style EV/CI final gate")
    print(f"  tasks: {len(candidates)} | samples/state: {args.samples_per_state}")
    print(f"  per task: up to {args.marginal_states} marginal + {args.random_states} random states")
    print(f"  marginal band: p(STAY) in [{args.marginal_low:.2f}, {args.marginal_high:.2f}]")
    print(f"  min effective visits/state: {args.min_effective_visits:.1f}")
    print(f"  rebate sensitivity factors: {', '.join(f'{x:.2f}' for x in factors)}")
    print("  baseline uses the persisted 2% gross-rake model")
    print("  rebate cases add the empirically calibrated cashback on Hero contribution")
    print("  read-only: persistent CFR state/RNG/snapshots are not modified")

    reports = []
    all_rows: list[dict] = []
    for i, row in enumerate(candidates, 1):
        n = int(row["n"])
        flop_index = int(row["flop_index"])
        report = _task_report(
            root=root,
            task=task_map[(n, flop_index)],
            source_sha=source_sha,
            samples_per_state=args.samples_per_state,
            marginal_states=args.marginal_states,
            random_states=args.random_states,
            marginal_low=args.marginal_low,
            marginal_high=args.marginal_high,
            min_effective_visits=args.min_effective_visits,
            rake_pct=args.rake,
            nominal_rb=args.nominal_rb,
            pvi_factors=factors,
            seed=args.seed + i * 100003,
        )
        report["prior_changed_pct"] = float(row["changed_pct"])
        reports.append(report)
        all_rows.extend(report["rows"])
        center = f"{factors[len(factors)//2]:.4f}"
        local = _summarize_rows(report["rows"], center)
        print(
            f"  [{i:02d}/{len(candidates):02d}] N={n} flop={flop_index:04d} "
            f"prior_change={float(row['changed_pct']):.4f}% "
            f"marginal conf_mismatch={local['marginal']['confident_mismatches']}/"
            f"{local['marginal']['confident_states']} "
            f"random conf_mismatch={local['random']['confident_mismatches']}/"
            f"{local['random']['confident_states']}",
            flush=True,
        )

    baseline = _summarize_rows(all_rows, None)
    by_factor = {f"{f:.4f}": _summarize_rows(all_rows, f"{f:.4f}") for f in factors}
    payload = {
        "format": "DeepPot conditional DeepKK-style final EV/CI gate",
        "analysis_csv": str(analysis_csv),
        "candidate_rule": f"top {args.top_per_n} unstable tasks per N={args.n_min}..{args.n_max}",
        "rake_pct": args.rake,
        "nominal_rakeback": args.nominal_rb,
        "pvi_factors": factors,
        "samples_per_state": args.samples_per_state,
        "min_effective_visits": args.min_effective_visits,
        "baseline": baseline,
        "rebate_sensitivity": by_factor,
        "tasks": reports,
    }
    out_json = out_dir / "deepkk_final_gate.json"
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    print("\nOverall baseline (2% gross rake, no Hero rebate shift):")
    for s in ("marginal", "random"):
        x = baseline[s]
        print(
            f"  {s}: eligible={x['eligible_states']}/{x['sampled_states']} "
            f"confident={x['confident_states']} confident_mismatch={x['confident_mismatches']} "
            f"({x['mismatch_pct_of_confident']:.3f}% of confident)"
        )
    print("Rebate sensitivity:")
    for factor in factors:
        fk = f"{factor:.4f}"
        effective = 100.0 * args.nominal_rb * factor
        cashback = 100.0 * args.rake * args.nominal_rb * factor
        print(f"  factor={factor:.2f} effectiveRB~{effective:.1f}% cashback/contrib={cashback:.3f}%")
        for s in ("marginal", "random"):
            x = by_factor[fk][s]
            print(
                f"    {s}: eligible={x['eligible_states']}/{x['sampled_states']} "
                f"confident={x['confident_states']} confident_mismatch={x['confident_mismatches']} "
                f"({x['mismatch_pct_of_confident']:.3f}% of confident)"
            )
    print(f"JSON: {out_json}")


if __name__ == "__main__":
    main()
