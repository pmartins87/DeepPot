from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

from deeppot import continuous_training_fast_v2 as ct
from deeppot.continuous_runner_fast_v2 import production_source_sha256
from deeppot.multiway_response import MultiwayResponseValidator
from deeppot.state_space import decision_scenario_count

from analyze_deepkk_final_gate_conditional import _conditional_gap_samples, _weighted_mean_ci95


def _build_task_context(root: Path, task: ct.Task, source_sha: str, rake_pct: float):
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
    for key in range(expected):
        node = solver.nodes.get(key)
        policy[key] = (0.5, 0.5) if node is None else node.average_strategy()

    validator = MultiwayResponseValidator(
        num_players=task.n,
        flop=solver.flop,
        policy=policy,
        rake_pct=rake_pct,
        rake_cap=None,
        seed=1,
    )

    representative_hole: dict[int, tuple] = {}
    for raw_hole, sid in validator._raw_hole_to_state_id.items():
        representative_hole.setdefault(sid, raw_hole)
    if len(representative_hole) != validator.hole_state_count:
        raise RuntimeError("failed to build representative hole map")

    node_by_public: dict[int, int] = {}
    for idx, node in enumerate(validator.nodes):
        if node.public_id is not None:
            node_by_public[node.public_id] = idx

    return solver, iterations, policy, validator, representative_hole, node_by_public


def _quantile(xs: list[float], q: float) -> float:
    if not xs:
        return 0.0
    ys = sorted(xs)
    if len(ys) == 1:
        return ys[0]
    pos = q * (len(ys) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return ys[lo]
    f = pos - lo
    return ys[lo] * (1.0 - f) + ys[hi] * f


def main() -> None:
    ap = argparse.ArgumentParser(description="High-sample confirmation of SEL3000 DeepKK-style sampled mismatches")
    ap.add_argument("--training-root", default=r"C:\DeepPot\runs\continuous_master_fast_v2")
    ap.add_argument(
        "--gate-json",
        default=r"C:\DeepPot\runs\continuous_master_fast_v2\analysis\deepkk_final_gate_SEL3000\deepkk_final_gate.json",
    )
    ap.add_argument("--samples-per-state", type=int, default=5000)
    ap.add_argument("--min-effective-visits", type=float, default=100.0)
    ap.add_argument("--rake", type=float, default=0.02)
    # This is the directly observed session calibration: about 0.70% cashback
    # on Hero contribution. Keeping it explicit avoids pretending that the
    # rebate itself proves a particular hidden PVI or gross-rake formula.
    ap.add_argument("--cashback-per-contribution", type=float, default=0.007)
    ap.add_argument("--seed", type=int, default=190927)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    if args.samples_per_state <= 0:
        raise ValueError("samples-per-state must be positive")
    if args.min_effective_visits < 0:
        raise ValueError("min-effective-visits must be non-negative")

    root = Path(args.training_root).resolve()
    gate_path = Path(args.gate_json).resolve()
    gate = json.loads(gate_path.read_text(encoding="utf-8"))

    targets: list[dict] = []
    seen: set[tuple[int, int, int]] = set()
    for report in gate.get("tasks", []):
        n = int(report["n"])
        flop_index = int(report["flop_index"])
        for row in report.get("rows", []):
            center = row.get("factors", {}).get("0.7000", {})
            selected = bool(row.get("baseline_confident_mismatch", 0)) or bool(center.get("confident_mismatch", 0))
            if not selected:
                continue
            key = int(row["key"])
            ident = (n, flop_index, key)
            if ident in seen:
                continue
            seen.add(ident)
            targets.append(
                {
                    "n": n,
                    "flop_index": flop_index,
                    "key": key,
                    "stratum": row.get("stratum", ""),
                    "prior_solver_p_stay": float(row.get("solver_p_stay", 0.5)),
                    "prior_baseline_gap": float(row.get("baseline_gap", 0.0)),
                    "prior_ci95": float(row.get("ci95", 0.0)),
                }
            )

    if not targets:
        raise RuntimeError("no baseline/0.70 confident mismatches found in gate JSON")

    task_map = {(t.n, t.flop_index): t for t in ct._all_tasks()}
    source_sha = production_source_sha256()
    grouped: dict[tuple[int, int], list[dict]] = {}
    for t in targets:
        grouped.setdefault((t["n"], t["flop_index"]), []).append(t)

    print("DeepPot targeted high-sample mismatch confirmation")
    print(f"  source gate: {gate_path}")
    print(f"  unique target states: {len(targets)}")
    print(f"  samples/state: {args.samples_per_state:,}")
    print(f"  minimum effective visits: {args.min_effective_visits:.1f}")
    print(f"  baseline gross-rake model: {100.0*args.rake:.2f}%")
    print(f"  observed cashback shift: {100.0*args.cashback_per_contribution:.3f}% of Hero contribution")
    print("  read-only: persistent CFR state/RNG/snapshots are not modified")

    results: list[dict] = []
    done = 0
    for (n, flop_index), rr in sorted(grouped.items()):
        task = task_map[(n, flop_index)]
        solver, iterations, policy, validator, representative_hole, node_by_public = _build_task_context(
            root, task, source_sha, args.rake
        )
        for target in rr:
            key = int(target["key"])
            public_id, hole_state_id = divmod(key, solver.hole_state_count)
            p_stay = float(policy[key][1])
            rng = random.Random(args.seed + n * 100000000 + flop_index * 10000 + key)
            samples = _conditional_gap_samples(
                validator=validator,
                public_id=public_id,
                hole_state_id=hole_state_id,
                samples=args.samples_per_state,
                rng=rng,
                representative_hole=representative_hole,
                node_by_public=node_by_public,
            )
            mean_gap, ci95, n_eff = _weighted_mean_ci95(samples)
            eligible = n_eff >= args.min_effective_visits and math.isfinite(ci95)
            solver_stay = p_stay >= 0.5

            baseline_best_stay = mean_gap > 0.0
            baseline_confident = eligible and abs(mean_gap) > ci95
            baseline_mismatch = baseline_confident and solver_stay != baseline_best_stay

            rebate_shift = float(n) * args.cashback_per_contribution
            rebate_gap = mean_gap + rebate_shift
            rebate_best_stay = rebate_gap > 0.0
            rebate_confident = eligible and abs(rebate_gap) > ci95
            rebate_mismatch = rebate_confident and solver_stay != rebate_best_stay

            rec = {
                **target,
                "iterations_completed": int(iterations),
                "solver_p_stay": p_stay,
                "solver_action": "STAY" if solver_stay else "FOLD",
                "effective_visits": n_eff,
                "gap": mean_gap,
                "ci95": ci95,
                "baseline_ev_best": "STAY" if baseline_best_stay else "FOLD",
                "baseline_confident": int(baseline_confident),
                "baseline_confirmed_mismatch": int(baseline_mismatch),
                "cashback_shift": rebate_shift,
                "rebate_gap": rebate_gap,
                "rebate_ev_best": "STAY" if rebate_best_stay else "FOLD",
                "rebate_confident": int(rebate_confident),
                "rebate_confirmed_mismatch": int(rebate_mismatch),
            }
            results.append(rec)
            done += 1
            print(
                f"  [{done:02d}/{len(targets):02d}] N={n} flop={flop_index:04d} key={key} "
                f"pStay={p_stay:.4f} gap={mean_gap:+.5f} +/-{ci95:.5f} nEff={n_eff:.1f} "
                f"base={'MISMATCH' if baseline_mismatch else 'ok'} "
                f"rebate={'MISMATCH' if rebate_mismatch else 'ok'}",
                flush=True,
            )

    base_conf = [r for r in results if r["baseline_confident"]]
    base_mm = [r for r in results if r["baseline_confirmed_mismatch"]]
    rb_conf = [r for r in results if r["rebate_confident"]]
    rb_mm = [r for r in results if r["rebate_confirmed_mismatch"]]
    abs_base = [abs(float(r["gap"])) for r in base_mm]
    abs_rb = [abs(float(r["rebate_gap"])) for r in rb_mm]

    summary = {
        "target_states": len(results),
        "samples_per_state": args.samples_per_state,
        "min_effective_visits": args.min_effective_visits,
        "rake_pct": args.rake,
        "cashback_per_contribution": args.cashback_per_contribution,
        "baseline_confident": len(base_conf),
        "baseline_confirmed_mismatches": len(base_mm),
        "rebate_confident": len(rb_conf),
        "rebate_confirmed_mismatches": len(rb_mm),
        "baseline_mismatch_abs_gap_median": _quantile(abs_base, 0.50),
        "baseline_mismatch_abs_gap_p95": _quantile(abs_base, 0.95),
        "baseline_mismatch_abs_gap_max": max(abs_base) if abs_base else 0.0,
        "rebate_mismatch_abs_gap_median": _quantile(abs_rb, 0.50),
        "rebate_mismatch_abs_gap_p95": _quantile(abs_rb, 0.95),
        "rebate_mismatch_abs_gap_max": max(abs_rb) if abs_rb else 0.0,
    }

    out_dir = Path(args.out).resolve() if args.out else root / "analysis" / "deepkk_confirm_mismatches_SEL3000"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_json = out_dir / "confirmed_mismatches.json"
    out_json.write_text(json.dumps({"summary": summary, "states": results}, indent=2, sort_keys=True), encoding="utf-8")

    print("\nSummary:")
    print(f"  baseline confirmed mismatches: {len(base_mm)}/{len(results)} targets")
    print(f"  observed-cashback confirmed mismatches: {len(rb_mm)}/{len(results)} targets")
    print(
        "  baseline |gap| among confirmed mismatches: "
        f"median={summary['baseline_mismatch_abs_gap_median']:.6f} "
        f"p95={summary['baseline_mismatch_abs_gap_p95']:.6f} max={summary['baseline_mismatch_abs_gap_max']:.6f} antes"
    )
    print(
        "  rebate |gap| among confirmed mismatches: "
        f"median={summary['rebate_mismatch_abs_gap_median']:.6f} "
        f"p95={summary['rebate_mismatch_abs_gap_p95']:.6f} max={summary['rebate_mismatch_abs_gap_max']:.6f} antes"
    )
    print(f"JSON: {out_json}")


if __name__ == "__main__":
    main()
