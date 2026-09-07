from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .multiway_response import MultiwayResponseValidator, load_policy_csv, parse_flop

MULTIWAY_REFINER_VERSION = "2026-09-07.1"


@dataclass(frozen=True)
class MultiwayRefinementRound:
    round_index: int
    seed: int
    samples: int
    alpha: float
    br_stay_states_by_seat: tuple[int, ...]
    unreachable_infosets_by_seat: tuple[int, ...]
    mean_abs_probability_update: float
    max_abs_probability_update: float


def _learn_pure_best_responses(
    validator: MultiwayResponseValidator,
    *,
    samples: int,
) -> tuple[list[bool], tuple[int, ...], tuple[int, ...]]:
    """Learn one pure unilateral BR action at every exact infoset.

    Opponent actions are integrated exactly over the public FOLD/STAY tree for
    each sampled chance deal, exactly as in the frozen P4C response validator.
    The returned action vector is indexed by the same dense exact infoset key as
    the policy. No card abstraction is introduced.
    """

    if samples <= 0:
        raise ValueError("samples must be positive")

    n = validator.num_players
    h = validator.hole_state_count
    node_count = len(validator.nodes)
    expected = validator.expected_infosets

    values = [0.0] * (node_count * n)
    p_stay_by_node = [0.0] * node_count
    reach = [0.0] * node_count

    weight_sum = [0.0] * expected
    fold_value_sum = [0.0] * expected
    stay_value_sum = [0.0] * expected

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
            actor = node.actor
            r = reach[idx]
            if r <= 0.0:
                continue
            key = node.public_id * h + hole_ids[actor]
            weight_sum[key] += r
            fold_value_sum[key] += r * values[node.fold_child * n + actor]
            stay_value_sum[key] += r * values[node.stay_child * n + actor]

    br_stay = [False] * expected
    stay_counts = [0] * n
    unreachable = [0] * n

    for key in range(expected):
        public_id, _hole_id = divmod(key, h)
        actor = validator.actor_by_public[public_id]
        if weight_sum[key] > 0.0:
            choose_stay = stay_value_sum[key] > fold_value_sum[key]
        else:
            unreachable[actor] += 1
            choose_stay = validator.policy[key][1] >= 0.5
        br_stay[key] = choose_stay
        if choose_stay:
            stay_counts[actor] += 1

    return br_stay, tuple(stay_counts), tuple(unreachable)


def refine_policy(
    *,
    num_players: int,
    flop,
    initial_policy: dict[int, tuple[float, float]],
    rake_pct: float,
    rake_cap: float | None,
    rounds: int = 32,
    samples_per_round: int = 50_000,
    prior_weight: int = 4,
    seed_base: int = 9_402_026,
) -> tuple[dict[int, tuple[float, float]], list[MultiwayRefinementRound]]:
    """The one finite response-directed correction allowed by P4C.

    This is sampled multi-player fictitious-response averaging over the exact
    information sets. At each fixed round:

    1. learn every seat's pure unilateral best response against the CURRENT
       average policy using the exact public action tree;
    2. move each behavioral probability toward that seat's response with
       alpha_t = 1 / (prior_weight + t).

    The initial CFR consensus acts as `prior_weight` pseudo-iterations. The
    schedule is finite and fixed before the corrected P4C rerun; there is no
    early stopping, parameter sweep, texture-specific tuning or card bucketing.
    """

    if not 3 <= num_players <= 8:
        raise ValueError("multiway refinement requires 3..8 players")
    if rounds <= 0:
        raise ValueError("rounds must be positive")
    if samples_per_round <= 0:
        raise ValueError("samples_per_round must be positive")
    if prior_weight <= 0:
        raise ValueError("prior_weight must be positive")

    policy = dict(initial_policy)
    audit: list[MultiwayRefinementRound] = []

    for round_index in range(1, rounds + 1):
        seed = seed_base + round_index
        validator = MultiwayResponseValidator(
            num_players=num_players,
            flop=flop,
            policy=policy,
            rake_pct=rake_pct,
            rake_cap=rake_cap,
            seed=seed,
        )
        br_stay, stay_counts, unreachable = _learn_pure_best_responses(
            validator,
            samples=samples_per_round,
        )

        alpha = 1.0 / (prior_weight + round_index)
        deltas: list[float] = []
        next_policy: dict[int, tuple[float, float]] = {}
        for key in range(validator.expected_infosets):
            old_stay = policy[key][1]
            target = 1.0 if br_stay[key] else 0.0
            new_stay = (1.0 - alpha) * old_stay + alpha * target
            new_stay = min(1.0, max(0.0, new_stay))
            next_policy[key] = (1.0 - new_stay, new_stay)
            deltas.append(abs(new_stay - old_stay))

        policy = next_policy
        audit.append(
            MultiwayRefinementRound(
                round_index=round_index,
                seed=seed,
                samples=samples_per_round,
                alpha=alpha,
                br_stay_states_by_seat=stay_counts,
                unreachable_infosets_by_seat=unreachable,
                mean_abs_probability_update=(sum(deltas) / len(deltas)) if deltas else 0.0,
                max_abs_probability_update=max(deltas, default=0.0),
            )
        )

    return policy, audit


def write_policy_csv(
    path: str | Path,
    policy: dict[int, tuple[float, float]],
    hole_state_count: int,
) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "infoset_key",
            "public_scenario_id",
            "exact_hole_state_id",
            "p_fold",
            "p_stay",
            "visits",
        ])
        for key in sorted(policy):
            public_id, hole_id = divmod(key, hole_state_count)
            p_fold, p_stay = policy[key]
            writer.writerow([
                key,
                public_id,
                hole_id,
                f"{p_fold:.12g}",
                f"{p_stay:.12g}",
                0,
            ])


def main() -> None:
    ap = argparse.ArgumentParser(description="Finite exact multiway damped-response refinement")
    ap.add_argument("--players", type=int, required=True)
    ap.add_argument("--policy", required=True)
    ap.add_argument("--flop", required=True)
    ap.add_argument("--rake-pct", type=float, default=0.02)
    ap.add_argument("--rake-cap", type=float, default=None)
    ap.add_argument("--rounds", type=int, default=32)
    ap.add_argument("--samples-per-round", type=int, required=True)
    ap.add_argument("--prior-weight", type=int, default=4)
    ap.add_argument("--seed-base", type=int, default=9402026)
    ap.add_argument("--out-policy", required=True)
    ap.add_argument("--out-audit", required=True)
    args = ap.parse_args()

    flop = parse_flop(args.flop)
    initial = load_policy_csv(args.policy)
    refined, rounds = refine_policy(
        num_players=args.players,
        flop=flop,
        initial_policy=initial,
        rake_pct=args.rake_pct,
        rake_cap=args.rake_cap,
        rounds=args.rounds,
        samples_per_round=args.samples_per_round,
        prior_weight=args.prior_weight,
        seed_base=args.seed_base,
    )
    validator = MultiwayResponseValidator(
        num_players=args.players,
        flop=flop,
        policy=refined,
        rake_pct=args.rake_pct,
        rake_cap=args.rake_cap,
        seed=args.seed_base,
    )
    write_policy_csv(args.out_policy, refined, validator.hole_state_count)
    payload = {
        "refiner_version": MULTIWAY_REFINER_VERSION,
        "num_players": args.players,
        "flop": [str(card) for card in flop],
        "rounds": args.rounds,
        "samples_per_round": args.samples_per_round,
        "prior_weight": args.prior_weight,
        "seed_base": args.seed_base,
        "rake_pct": args.rake_pct,
        "rake_cap": args.rake_cap,
        "strategic_card_abstraction": "none",
        "exact_symmetry_reduction": "global_suit_isomorphism_only",
        "method": "finite_multiplayer_fictitious_response_average",
        "round_audit": [asdict(round_) for round_ in rounds],
    }
    Path(args.out_audit).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
