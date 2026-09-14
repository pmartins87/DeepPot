from __future__ import annotations

import argparse
import json
import math
import random
from collections import defaultdict
from pathlib import Path

from deeppot import continuous_training_fast_v2 as ct
from deeppot.continuous_runner_fast_v2 import production_source_sha256
from deeppot.multiway_response import MultiwayResponseValidator
from deeppot.state_space import decision_scenario_count

Q_BINS = (
    (0.50, 0.55, "50-55"),
    (0.55, 0.60, "55-60"),
    (0.60, 0.70, "60-70"),
    (0.70, 0.80, "70-80"),
    (0.80, 0.90, "80-90"),
    (0.90, 0.95, "90-95"),
    (0.95, 0.99, "95-99"),
    (0.99, 1.0000000001, "99-100"),
)


def _weighted_mean_ci95(samples: list[tuple[float, float]]) -> tuple[float, float, float]:
    sw = sum(w for _, w in samples)
    sw2 = sum(w * w for _, w in samples)
    if sw <= 0.0 or sw2 <= 0.0:
        return 0.0, float("inf"), 0.0
    mean = sum(x * w for x, w in samples) / sw
    second = sum(x * x * w for x, w in samples) / sw
    var = max(0.0, second - mean * mean)
    n_eff = (sw * sw) / sw2
    if n_eff <= 1.0:
        return mean, float("inf"), n_eff
    return mean, 1.959963984540054 * math.sqrt(var / n_eff), n_eff


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


def _bin_label(q: float) -> str | None:
    for lo, hi, label in Q_BINS:
        if lo <= q < hi:
            return label
    return None


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


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2 or len(xs) != len(ys):
        return None
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]
    vx = sum(x * x for x in dx)
    vy = sum(y * y for y in dy)
    if vx <= 0.0 or vy <= 0.0:
        return None
    return sum(a * b for a, b in zip(dx, dy)) / math.sqrt(vx * vy)


def _summary(rows: list[dict]) -> dict:
    eligible = [r for r in rows if r["eligible"]]
    confident = [r for r in eligible if r["confident"]]
    live_confident = [r for r in eligible if r["live_confident"]]
    point_matches = sum(int(r["point_match"]) for r in eligible)
    conf_matches = sum(int(r["confident_match"]) for r in confident)
    live_point_matches = sum(int(r["live_point_match"]) for r in eligible)
    live_conf_matches = sum(int(r["live_confident_match"]) for r in live_confident)
    gmm = [float(r["greedy_minus_mixed_ev"]) for r in eligible]
    lgmm = [float(r["live_greedy_minus_mixed_ev"]) for r in eligible]
    xs = [float(r["p_stay"]) for r in eligible]
    ys = [float(r["gap_stay_minus_fold"]) for r in eligible]
    return {
        "sampled": len(rows),
        "eligible": len(eligible),
        "confident": len(confident),
        "point_match_pct": 100.0 * point_matches / max(1, len(eligible)),
        "confident_match_pct": 100.0 * conf_matches / max(1, len(confident)),
        "confident_mismatches": len(confident) - conf_matches,
        "mean_greedy_minus_mixed_ev": sum(gmm) / max(1, len(gmm)),
        "live_confident": len(live_confident),
        "live_point_match_pct": 100.0 * live_point_matches / max(1, len(eligible)),
        "live_confident_match_pct": 100.0 * live_conf_matches / max(1, len(live_confident)),
        "live_confident_mismatches": len(live_confident) - live_conf_matches,
        "live_mean_greedy_minus_mixed_ev": sum(lgmm) / max(1, len(lgmm)),
        "pearson_pstay_vs_gap": _pearson(xs, ys),
    }


def _task_report(
    *,
    root: Path,
    task: ct.Task,
    source_sha: str,
    states_per_stratum: int,
    samples_per_state: int,
    min_effective_visits: float,
    rake_pct: float,
    cashback_per_contribution: float,
    seed: int,
) -> dict:
    config = ct.ContinuousConfig(seed=123, rake_pct=rake_pct, rake_cap=None, cfr_plus=True, linear_average=True)
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
        seed=seed,
    )
    representative_hole: dict[int, tuple] = {}
    for raw_hole, sid in validator._raw_hole_to_state_id.items():
        representative_hole.setdefault(sid, raw_hole)
    node_by_public = {node.public_id: idx for idx, node in enumerate(validator.nodes) if node.public_id is not None}

    populations: dict[tuple[str, str], list[int]] = defaultdict(list)
    for key, (_pf, ps) in policy.items():
        label = _bin_label(max(ps, 1.0 - ps))
        if label is None:
            continue
        public_id, _ = divmod(key, solver.hole_state_count)
        actor = validator.actor_by_public[public_id]
        group = "last" if actor == task.n - 1 else "earlier"
        populations[(label, group)].append(key)

    rng = random.Random(seed)
    chosen: list[tuple[int, str, str]] = []
    for _lo, _hi, label in Q_BINS:
        for group in ("earlier", "last"):
            pop = populations.get((label, group), [])
            if not pop:
                continue
            keys = pop if len(pop) <= states_per_stratum else rng.sample(pop, states_per_stratum)
            chosen.extend((key, label, group) for key in keys)

    rows: list[dict] = []
    live_shift = task.n * cashback_per_contribution
    for key, band, group in chosen:
        public_id, hole_state_id = divmod(key, solver.hole_state_count)
        actor = validator.actor_by_public[public_id]
        p_stay = policy[key][1]
        greedy_stay = p_stay >= 0.5
        raw = _conditional_gap_samples(
            validator=validator,
            public_id=public_id,
            hole_state_id=hole_state_id,
            samples=samples_per_state,
            rng=rng,
            representative_hole=representative_hole,
            node_by_public=node_by_public,
        )
        gap, ci95, n_eff = _weighted_mean_ci95(raw)
        eligible = n_eff >= min_effective_visits and math.isfinite(ci95)
        best_stay = gap > 0.0
        confident = eligible and abs(gap) > ci95
        point_match = greedy_stay == best_stay
        live_gap = gap + live_shift
        live_best_stay = live_gap > 0.0
        live_confident = eligible and abs(live_gap) > ci95
        live_point_match = greedy_stay == live_best_stay
        if greedy_stay:
            greedy_minus_mixed = (1.0 - p_stay) * gap
            live_greedy_minus_mixed = (1.0 - p_stay) * live_gap
        else:
            greedy_minus_mixed = -p_stay * gap
            live_greedy_minus_mixed = -p_stay * live_gap
        rows.append({
            "n": task.n,
            "flop_index": task.flop_index,
            "key": key,
            "public_id": public_id,
            "hole_state_id": hole_state_id,
            "actor": actor,
            "actor_group": group,
            "band": band,
            "p_stay": p_stay,
            "majority_probability": max(p_stay, 1.0 - p_stay),
            "greedy_action": "STAY" if greedy_stay else "FOLD",
            "gap_stay_minus_fold": gap,
            "ci95": ci95,
            "effective_visits": n_eff,
            "eligible": int(eligible),
            "ev_best_action": "STAY" if best_stay else "FOLD",
            "point_match": int(point_match),
            "confident": int(confident),
            "confident_match": int(confident and point_match),
            "confident_mismatch": int(confident and not point_match),
            "greedy_minus_mixed_ev": greedy_minus_mixed,
            "live_gap_stay_minus_fold": live_gap,
            "live_ev_best_action": "STAY" if live_best_stay else "FOLD",
            "live_point_match": int(live_point_match),
            "live_confident": int(live_confident),
            "live_confident_match": int(live_confident and live_point_match),
            "live_confident_mismatch": int(live_confident and not live_point_match),
            "live_greedy_minus_mixed_ev": live_greedy_minus_mixed,
        })
    return {
        "n": task.n,
        "flop_index": task.flop_index,
        "iterations_completed": iterations,
        "sampled_states": len(rows),
        "rows": rows,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="SEL3500 audit: does CFR majority frequency predict the EV-best pure action?")
    ap.add_argument("--training-root", default=r"C:\DeepPot\runs\continuous_master_fast_v2")
    ap.add_argument("--tasks-per-n", type=int, default=2)
    ap.add_argument("--states-per-stratum", type=int, default=3)
    ap.add_argument("--samples-per-state", type=int, default=1000)
    ap.add_argument("--min-effective-visits", type=float, default=50.0)
    ap.add_argument("--seed", type=int, default=9142026)
    ap.add_argument("--rake", type=float, default=0.02)
    ap.add_argument("--cashback-per-contribution", type=float, default=0.007)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    root = Path(args.training_root).resolve()
    source_sha = production_source_sha256()
    tasks = _choose_tasks(args.tasks_per_n, args.seed)
    out_dir = Path(args.out) if args.out else root / "analysis" / "frequency_ev_alignment_SEL3500"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("DeepPot SEL3500 CFR-frequency vs conditional-EV alignment audit")
    print(f"  tasks: {len(tasks)} ({args.tasks_per_n} random canonical flops per N=2..8)")
    print(f"  states/majority-band/actor-group/task: {args.states_per_stratum}")
    print(f"  conditional samples/state: {args.samples_per_state}")
    print(f"  min effective visits: {args.min_effective_visits:.1f}")
    print(f"  baseline rake: {100*args.rake:.2f}% | observed cashback/contribution: {100*args.cashback_per_contribution:.3f}%")
    print("  opponent profile: persisted SEL3500 average CFR mixed policy")
    print("  read-only: CFR state/RNG/snapshots are not modified")

    reports: list[dict] = []
    all_rows: list[dict] = []
    for i, task in enumerate(tasks, 1):
        report = _task_report(
            root=root,
            task=task,
            source_sha=source_sha,
            states_per_stratum=args.states_per_stratum,
            samples_per_state=args.samples_per_state,
            min_effective_visits=args.min_effective_visits,
            rake_pct=args.rake,
            cashback_per_contribution=args.cashback_per_contribution,
            seed=args.seed + i * 1000003,
        )
        reports.append(report)
        all_rows.extend(report["rows"])
        s = _summary(report["rows"])
        print(
            f"  [{i:02d}/{len(tasks):02d}] N={task.n} flop={task.flop_index:04d} "
            f"states={s['sampled']} eligible={s['eligible']} point_match={s['point_match_pct']:.1f}% "
            f"conf_match={s['confident_match_pct']:.1f}%",
            flush=True,
        )

    by_band: dict[str, dict] = {}
    for _lo, _hi, label in Q_BINS:
        rr = [r for r in all_rows if r["band"] == label]
        by_band[label] = _summary(rr)
    by_actor = {g: _summary([r for r in all_rows if r["actor_group"] == g]) for g in ("earlier", "last")}
    global_summary = _summary(all_rows)

    payload = {
        "format": "DeepPot SEL3500 CFR-frequency vs conditional-EV alignment audit",
        "tasks_per_n": args.tasks_per_n,
        "states_per_stratum": args.states_per_stratum,
        "samples_per_state": args.samples_per_state,
        "min_effective_visits": args.min_effective_visits,
        "rake_pct": args.rake,
        "cashback_per_contribution": args.cashback_per_contribution,
        "opponent_profile": "SEL3500 average CFR mixed policy",
        "global": global_summary,
        "by_majority_band": by_band,
        "by_actor_group": by_actor,
        "tasks": reports,
    }
    out_json = out_dir / "frequency_ev_alignment.json"
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    print("\nBy CFR majority probability (baseline | observed-cashback):")
    for _lo, _hi, label in Q_BINS:
        s = by_band[label]
        print(
            f"  {label}%: eligible={s['eligible']} conf={s['confident']} | "
            f"point match {s['point_match_pct']:.1f}% / {s['live_point_match_pct']:.1f}% | "
            f"confident match {s['confident_match_pct']:.1f}% / {s['live_confident_match_pct']:.1f}% | "
            f"mean greedy-mixed EV {s['mean_greedy_minus_mixed_ev']:+.4f} / {s['live_mean_greedy_minus_mixed_ev']:+.4f} ante"
        )

    print("\nActor split:")
    for g in ("earlier", "last"):
        s = by_actor[g]
        print(
            f"  {g}: eligible={s['eligible']} | point match={s['point_match_pct']:.1f}% | "
            f"confident match={s['confident_match_pct']:.1f}% | "
            f"mean greedy-mixed EV={s['mean_greedy_minus_mixed_ev']:+.4f} ante"
        )

    g = global_summary
    corr = g["pearson_pstay_vs_gap"]
    corr_text = "n/a" if corr is None else f"{corr:.4f}"
    print("\nGlobal:")
    print(f"  eligible={g['eligible']} confident={g['confident']}")
    print(f"  greedy majority matches EV-best point estimate: {g['point_match_pct']:.2f}%")
    print(f"  among confident states, greedy majority matches EV-best: {g['confident_match_pct']:.2f}%")
    print(f"  mean EV(greedy)-EV(mixed) vs CFR profile: {g['mean_greedy_minus_mixed_ev']:+.5f} ante")
    print(f"  Pearson p(STAY) vs EV(STAY-FOLD): {corr_text}")
    print(f"  observed-cashback point match: {g['live_point_match_pct']:.2f}%")
    print(f"  observed-cashback confident match: {g['live_confident_match_pct']:.2f}%")
    print(f"JSON: {out_json}")


if __name__ == "__main__":
    main()
