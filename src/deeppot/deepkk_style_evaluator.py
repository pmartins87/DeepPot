from __future__ import annotations

import argparse
import csv
import gzip
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .multiway_response import MultiwayResponseValidator, parse_flop


@dataclass(frozen=True)
class WeightedMoments:
    sum_w: float = 0.0
    sum_w2: float = 0.0
    sum_x: float = 0.0
    sum_x2: float = 0.0


def load_policy_gzip(path: str | Path) -> dict[int, tuple[float, float]]:
    out: dict[int, tuple[float, float]] = {}
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            key = int(row["infoset_key"])
            out[key] = (float(row["p_fold"]), float(row["p_stay"]))
    return out


def _weighted_mean(sum_w: float, sum_x: float) -> float:
    return sum_x / sum_w if sum_w > 0.0 else 0.0


def _weighted_stderr(sum_w: float, sum_w2: float, sum_x: float, sum_x2: float) -> tuple[float | None, float]:
    if sum_w <= 0.0 or sum_w2 <= 0.0:
        return None, 0.0
    mean = sum_x / sum_w
    var = max(0.0, sum_x2 / sum_w - mean * mean)
    n_eff = (sum_w * sum_w) / sum_w2
    if n_eff <= 1.0:
        return None, n_eff
    return math.sqrt(var / n_eff), n_eff


def evaluate_policy_deepkk_style(
    *,
    num_players: int,
    flop,
    policy: Mapping[int, tuple[float, float]],
    samples: int,
    min_effective_visits: float,
    seed: int,
    rake_pct: float,
    rake_cap: float | None,
) -> tuple[list[dict], dict]:
    """DeepKK-style FOLD-vs-STAY audit for every exact infoset on one flop.

    This deliberately mirrors the DeepKK rule: estimate both action EVs under
    the trained base policy, compute an EV gap and CI95, use the statistically
    confident best action when available, otherwise retain the solver-average
    greedy action. It is not a best-response/exploitability gate.
    """

    if samples <= 0:
        raise ValueError("samples must be positive")
    if min_effective_visits < 0:
        raise ValueError("min_effective_visits must be non-negative")

    validator = MultiwayResponseValidator(
        num_players=num_players,
        flop=flop,
        policy=policy,
        rake_pct=rake_pct,
        rake_cap=rake_cap,
        seed=seed,
    )
    expected = validator.expected_infosets
    n = validator.num_players
    h = validator.hole_state_count
    node_count = len(validator.nodes)

    sum_w = [0.0] * expected
    sum_w2 = [0.0] * expected
    sum_fold = [0.0] * expected
    sum_stay = [0.0] * expected
    sum_gap = [0.0] * expected
    sum_gap2 = [0.0] * expected
    raw_opportunities = [0] * expected

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
            ev_fold = values[node.fold_child * n + actor]
            ev_stay = values[node.stay_child * n + actor]
            gap = ev_stay - ev_fold
            sum_w[key] += r
            sum_w2[key] += r * r
            sum_fold[key] += r * ev_fold
            sum_stay[key] += r * ev_stay
            sum_gap[key] += r * gap
            sum_gap2[key] += r * gap * gap
            raw_opportunities[key] += 1

    rows: list[dict] = []
    confident = 0
    covered = 0
    low_coverage = 0
    for key in range(expected):
        public_id, hole_id = divmod(key, h)
        w = sum_w[key]
        ev_fold = _weighted_mean(w, sum_fold[key])
        ev_stay = _weighted_mean(w, sum_stay[key])
        gap = _weighted_mean(w, sum_gap[key])
        stderr, n_eff = _weighted_stderr(w, sum_w2[key], sum_gap[key], sum_gap2[key])
        ci95 = None if stderr is None else 1.959963984540054 * stderr
        if w > 0.0:
            covered += 1
        low_cov = n_eff < min_effective_visits
        if low_cov:
            low_coverage += 1
        is_confident = ci95 is not None and abs(gap) > ci95 and not low_cov
        if is_confident:
            confident += 1

        solver_p_stay = float(policy[key][1])
        solver_action = "STAY" if solver_p_stay >= 0.5 else "FOLD"
        ev_best = "STAY" if gap > 0.0 else "FOLD"
        final_action = ev_best if is_confident else solver_action
        rows.append(
            {
                "num_players": num_players,
                "scenario_dense_id": public_id,
                "exact_hole_state_id": hole_id,
                "raw_opportunities": raw_opportunities[key],
                "effective_visits": n_eff,
                "reach_weight": w,
                "ev_fold_ante": ev_fold,
                "ev_stay_ante": ev_stay,
                "ev_gap_stay_minus_fold_ante": gap,
                "stderr_gap_ante": "" if stderr is None else stderr,
                "ci95_gap_ante": "" if ci95 is None else ci95,
                "solver_p_stay": solver_p_stay,
                "solver_greedy_action": solver_action,
                "ev_best_action": ev_best,
                "best_action_confident": int(is_confident),
                "low_coverage": int(low_cov),
                "final_action": final_action,
            }
        )

    summary = {
        "samples": samples,
        "seed": seed,
        "total_infosets": expected,
        "covered_infosets": covered,
        "low_coverage_infosets": low_coverage,
        "confident_best_action_infosets": confident,
        "confident_infosets_pct": 100.0 * confident / max(1, expected),
        "covered_infosets_pct": 100.0 * covered / max(1, expected),
        "decision_rule": "confident_EV_best_else_solver_average_greedy",
        "confidence_rule": "abs(EV_STAY-EV_FOLD)>CI95 and effective_visits>=minimum",
        "strategic_card_abstraction": "none",
    }
    return rows, summary


def write_rows(path: str | Path, rows: list[dict]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError("rows must not be empty")
    with p.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description="DeepKK-style EV/CI confidence audit for one DeepPot flop shard")
    ap.add_argument("--players", type=int, required=True)
    ap.add_argument("--flop", required=True)
    ap.add_argument("--policy-gz", required=True)
    ap.add_argument("--samples", type=int, required=True)
    ap.add_argument("--min-effective-visits", type=float, required=True)
    ap.add_argument("--seed", type=int, default=123)
    ap.add_argument("--rake-pct", type=float, required=True)
    ap.add_argument("--rake-cap", type=float, default=None)
    ap.add_argument("--out-csv", required=True)
    args = ap.parse_args()

    rows, summary = evaluate_policy_deepkk_style(
        num_players=args.players,
        flop=parse_flop(args.flop),
        policy=load_policy_gzip(args.policy_gz),
        samples=args.samples,
        min_effective_visits=args.min_effective_visits,
        seed=args.seed,
        rake_pct=args.rake_pct,
        rake_cap=args.rake_cap,
    )
    write_rows(args.out_csv, rows)
    print(summary)


if __name__ == "__main__":
    main()
