from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

from deeppot.cards import Card, enumerate_canonical_flops
from deeppot.exact_index import ExactFlopHoleIndex
from deeppot.multiway_response import MultiwayResponseValidator
from deeppot.state_space import decision_scenario_count

POPCOUNT = bytes(bin(i).count("1") for i in range(256))


def _cards_from_key(key):
    return tuple(Card(rank, suit) for rank, suit in key)


def _load_candidates(path: Path, top_per_n: int, n_min: int, n_max: int) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    out: list[dict] = []
    for n in range(n_min, n_max + 1):
        rr = [r for r in rows if int(r["n"]) == n]
        rr.sort(key=lambda r: float(r["changed_pct"]), reverse=True)
        out.extend(rr[:top_per_n])
    return out


def _task_policy_from_snapshot(
    *,
    snapshot_strategy: Path,
    n: int,
    flop_index: int,
    hole_counts: list[int],
) -> dict[int, tuple[float, float]]:
    scenarios = decision_scenario_count(n)
    raw = (snapshot_strategy / f"N{n}_final.bits").read_bytes()
    offset = 0
    for i in range(flop_index):
        infosets = scenarios * hole_counts[i]
        offset += (infosets + 7) // 8
    infosets = scenarios * hole_counts[flop_index]
    size = (infosets + 7) // 8
    chunk = raw[offset : offset + size]
    if len(chunk) != size:
        raise RuntimeError(f"truncated snapshot slice N={n} flop={flop_index}")
    policy: dict[int, tuple[float, float]] = {}
    for key in range(infosets):
        stay = bool(chunk[key >> 3] & (1 << (key & 7)))
        policy[key] = (0.0, 1.0) if stay else (1.0, 0.0)
    return policy


def _quantile_from_weighted_sums(sum_w: float, sum_w2: float, sum_gap: float, sum_gap2: float):
    if sum_w <= 0.0 or sum_w2 <= 0.0:
        return None, 0.0, 0.0
    mean = sum_gap / sum_w
    var = max(0.0, sum_gap2 / sum_w - mean * mean)
    n_eff = (sum_w * sum_w) / sum_w2
    if n_eff <= 1.0:
        return None, mean, n_eff
    stderr = math.sqrt(var / n_eff)
    return 1.959963984540054 * stderr, mean, n_eff


def audit_task(
    *,
    n: int,
    flop,
    policy: dict[int, tuple[float, float]],
    samples: int,
    seed: int,
    rake_pct: float,
    nominal_rb: float,
    pvi_factors: list[float],
    min_effective_visits: float,
) -> dict:
    validator = MultiwayResponseValidator(
        num_players=n,
        flop=flop,
        policy=policy,
        rake_pct=rake_pct,
        rake_cap=None,
        seed=seed,
    )
    expected = validator.expected_infosets
    h = validator.hole_state_count
    node_count = len(validator.nodes)

    sum_w = [0.0] * expected
    sum_w2 = [0.0] * expected
    sum_gap = [0.0] * expected
    sum_gap2 = [0.0] * expected
    values = [0.0] * (node_count * n)
    p_stay_by_node = [0.0] * node_count
    reach = [0.0] * node_count

    for _ in range(samples):
        holes, turn, river = validator._sample()
        hole_ids, _ = validator._fill_profile(
            holes=holes,
            turn=turn,
            river=river,
            values=values,
            p_stay_by_node=p_stay_by_node,
        )
        validator._fill_reach(p_stay_by_node, reach)
        for idx, node in enumerate(validator.nodes):
            if node.terminal:
                continue
            assert node.actor is not None and node.public_id is not None
            assert node.fold_child is not None and node.stay_child is not None
            r = reach[idx]
            if r <= 0.0:
                continue
            actor = node.actor
            key = node.public_id * h + hole_ids[actor]
            gap = values[node.stay_child * n + actor] - values[node.fold_child * n + actor]
            sum_w[key] += r
            sum_w2[key] += r * r
            sum_gap[key] += r * gap
            sum_gap2[key] += r * gap * gap

    factors = {}
    for factor in pvi_factors:
        # Empirical linear rebate model. With ante normalized to 1, STAY adds N
        # contribution units versus FOLD. The observed cashback per contribution
        # unit is rake_pct * nominal_rb * effective_relative_PVI.
        cashback_per_contribution = rake_pct * nominal_rb * factor
        gap_shift = float(n) * cashback_per_contribution
        covered = 0
        eligible = 0
        sign_flip_fold_to_stay = 0
        confident_reversal = 0
        current_greedy_diff = 0
        confident_current_greedy_diff = 0
        baseline_stay = 0
        rebate_stay = 0

        for key in range(expected):
            ci95, gap, n_eff = _quantile_from_weighted_sums(
                sum_w[key], sum_w2[key], sum_gap[key], sum_gap2[key]
            )
            if sum_w[key] <= 0.0:
                continue
            covered += 1
            if n_eff < min_effective_visits:
                continue
            eligible += 1
            rebate_gap = gap + gap_shift
            if gap > 0.0:
                baseline_stay += 1
            if rebate_gap > 0.0:
                rebate_stay += 1
            if gap <= 0.0 < rebate_gap:
                sign_flip_fold_to_stay += 1
                if ci95 is not None and gap + ci95 < 0.0 and rebate_gap - ci95 > 0.0:
                    confident_reversal += 1

            current_stay = policy[key][1] >= 0.5
            rebate_best_stay = rebate_gap > 0.0
            if current_stay != rebate_best_stay:
                current_greedy_diff += 1
                if ci95 is not None:
                    if rebate_best_stay and rebate_gap - ci95 > 0.0:
                        confident_current_greedy_diff += 1
                    elif (not rebate_best_stay) and rebate_gap + ci95 < 0.0:
                        confident_current_greedy_diff += 1

        factors[f"{factor:.4f}"] = {
            "effective_nominal_rakeback_pct_of_equal_pvi_benchmark": 100.0 * nominal_rb * factor,
            "cashback_per_contribution_pct": 100.0 * cashback_per_contribution,
            "stay_minus_fold_ev_shift_antes": gap_shift,
            "covered_infosets": covered,
            "eligible_infosets": eligible,
            "baseline_ev_best_stay_infosets": baseline_stay,
            "rebate_ev_best_stay_infosets": rebate_stay,
            "fold_to_stay_sign_flips": sign_flip_fold_to_stay,
            "fold_to_stay_sign_flip_pct": 100.0 * sign_flip_fold_to_stay / max(1, eligible),
            "confident_fold_to_stay_reversals": confident_reversal,
            "current_greedy_vs_rebate_ev_best_diffs": current_greedy_diff,
            "current_greedy_vs_rebate_ev_best_diff_pct": 100.0 * current_greedy_diff / max(1, eligible),
            "confident_current_greedy_vs_rebate_ev_best_diffs": confident_current_greedy_diff,
        }

    return {
        "n": n,
        "flop": [str(c) for c in flop],
        "samples": samples,
        "expected_infosets": expected,
        "hole_states": validator.hole_state_count,
        "public_scenarios": validator.public_scenarios,
        "rake_pct": rake_pct,
        "nominal_rakeback": nominal_rb,
        "min_effective_visits": min_effective_visits,
        "factors": factors,
    }


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Read-only DeepPot sensitivity audit for empirically calibrated rakeback"
    )
    ap.add_argument("--training-root", default=r"C:\DeepPot\runs\continuous_master_fast_v2")
    ap.add_argument("--snapshot", default="V2_SEL2500")
    ap.add_argument("--analysis-csv", default=r"C:\DeepPot\runs\continuous_master_fast_v2\analysis\V2_2000_to_V2_SEL2500\task_stability.csv")
    ap.add_argument("--top-per-n", type=int, default=3)
    ap.add_argument("--n-min", type=int, default=5)
    ap.add_argument("--n-max", type=int, default=8)
    ap.add_argument("--samples", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=12345)
    ap.add_argument("--rake", type=float, default=0.02)
    ap.add_argument("--nominal-rb", type=float, default=0.50)
    ap.add_argument("--pvi-factors", default="0.60,0.70,0.80")
    ap.add_argument("--min-effective-visits", type=float, default=25.0)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    if args.top_per_n <= 0 or args.samples <= 0:
        raise ValueError("top-per-n and samples must be positive")
    if not 0.0 <= args.rake < 1.0:
        raise ValueError("rake must be in [0,1)")
    if not 0.0 <= args.nominal_rb <= 1.0:
        raise ValueError("nominal-rb must be in [0,1]")

    factors = [float(x.strip()) for x in args.pvi_factors.split(",") if x.strip()]
    if not factors or any(x < 0.0 for x in factors):
        raise ValueError("pvi-factors must contain non-negative numbers")

    root = Path(args.training_root)
    strategy = root / "snapshots" / args.snapshot / "DeepPotRuntime" / "strategy"
    analysis_csv = Path(args.analysis_csv)
    if not strategy.exists():
        raise RuntimeError(f"snapshot strategy not found: {strategy}")
    if not analysis_csv.exists():
        raise RuntimeError(f"analysis CSV not found: {analysis_csv}")

    candidates = _load_candidates(analysis_csv, args.top_per_n, args.n_min, args.n_max)
    if not candidates:
        raise RuntimeError("no candidate tasks selected")

    flop_keys = enumerate_canonical_flops()
    flops = [_cards_from_key(k) for k in flop_keys]
    hole_counts = [len(ExactFlopHoleIndex.build(f)) for f in flops]

    out_dir = Path(args.out) if args.out else root / "analysis" / f"rakeback_sensitivity_{args.snapshot}"
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    print("DeepPot read-only rakeback sensitivity audit")
    print(f"  snapshot: {args.snapshot}")
    print(f"  candidates: {len(candidates)}")
    print(f"  samples/task: {args.samples:,}")
    print(f"  nominal rakeback: {100*args.nominal_rb:.1f}%")
    print(f"  PVI factors: {', '.join(f'{x:.2f}' for x in factors)}")
    print("  CFR state/RNG/snapshots are NOT modified")

    for i, row in enumerate(candidates, 1):
        n = int(row["n"])
        flop_index = int(row["flop_index"])
        policy = _task_policy_from_snapshot(
            snapshot_strategy=strategy,
            n=n,
            flop_index=flop_index,
            hole_counts=hole_counts,
        )
        report = audit_task(
            n=n,
            flop=flops[flop_index],
            policy=policy,
            samples=args.samples,
            seed=args.seed + i * 100003,
            rake_pct=args.rake,
            nominal_rb=args.nominal_rb,
            pvi_factors=factors,
            min_effective_visits=args.min_effective_visits,
        )
        report["flop_index"] = flop_index
        report["prior_changed_pct"] = float(row["changed_pct"])
        results.append(report)
        mid = factors[len(factors) // 2]
        m = report["factors"][f"{mid:.4f}"]
        print(
            f"  [{i:02d}/{len(candidates):02d}] N={n} flop={flop_index:04d} "
            f"prior_change={float(row['changed_pct']):.4f}% "
            f"factor={mid:.2f} flips={m['fold_to_stay_sign_flips']:,} "
            f"({m['fold_to_stay_sign_flip_pct']:.4f}%) "
            f"confident_reversals={m['confident_fold_to_stay_reversals']:,}",
            flush=True,
        )

    aggregate = {}
    for factor in factors:
        key = f"{factor:.4f}"
        agg = {
            "eligible_infosets": 0,
            "fold_to_stay_sign_flips": 0,
            "confident_fold_to_stay_reversals": 0,
            "current_greedy_vs_rebate_ev_best_diffs": 0,
            "confident_current_greedy_vs_rebate_ev_best_diffs": 0,
        }
        for r in results:
            m = r["factors"][key]
            for name in agg:
                agg[name] += int(m[name])
        agg["fold_to_stay_sign_flip_pct"] = 100.0 * agg["fold_to_stay_sign_flips"] / max(1, agg["eligible_infosets"])
        agg["current_greedy_vs_rebate_ev_best_diff_pct"] = 100.0 * agg["current_greedy_vs_rebate_ev_best_diffs"] / max(1, agg["eligible_infosets"])
        agg["effective_nominal_rakeback_pct_of_equal_pvi_benchmark"] = 100.0 * args.nominal_rb * factor
        agg["cashback_per_contribution_pct"] = 100.0 * args.rake * args.nominal_rb * factor
        aggregate[key] = agg

    payload = {
        "format": "DeepPot rakeback sensitivity audit",
        "snapshot": args.snapshot,
        "analysis_csv": str(analysis_csv),
        "candidate_rule": f"top {args.top_per_n} unstable tasks per N={args.n_min}..{args.n_max}",
        "rake_pct": args.rake,
        "nominal_rakeback": args.nominal_rb,
        "pvi_factors": factors,
        "model": "empirical_linear_cashback_on_player_contribution",
        "model_note": "cashback_per_contribution = rake_pct * nominal_rakeback * effective_relative_PVI; this is an empirical sensitivity model, not a claim about KKPoker's hidden per-hand PVI implementation",
        "aggregate": aggregate,
        "tasks": results,
    }
    out_json = out_dir / "rakeback_sensitivity.json"
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    print("\nAggregate:")
    for factor in factors:
        a = aggregate[f"{factor:.4f}"]
        print(
            f"  factor={factor:.2f} effectiveRB~{a['effective_nominal_rakeback_pct_of_equal_pvi_benchmark']:.1f}% "
            f"cashback/contrib={a['cashback_per_contribution_pct']:.3f}% "
            f"FOLD->STAY flips={a['fold_to_stay_sign_flips']:,}/{a['eligible_infosets']:,} "
            f"({a['fold_to_stay_sign_flip_pct']:.4f}%) "
            f"confident_reversals={a['confident_fold_to_stay_reversals']:,}"
        )
    print(f"\nJSON: {out_json}")


if __name__ == "__main__":
    main()
