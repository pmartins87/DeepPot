from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

from .cards import Card
from .multiway_refine import _learn_pure_best_responses, write_policy_csv
from .multiway_response import MultiwayResponseValidator, load_policy_csv, parse_flop

MULTIWAY_PED_VERSION = "2026-09-07.1"


@dataclass(frozen=True)
class PEDGradientEstimate:
    samples: int
    mean_sample_gap: float
    max_abs_gradient: float
    mean_abs_gradient: float
    nonzero_gradient_infosets: int


@dataclass(frozen=True)
class PEDRound:
    round_index: int
    br_seed: int
    gradient_seed: int
    br_samples: int
    gradient_samples: int
    max_coordinate_step: float
    gradient: PEDGradientEstimate
    br_stay_states_by_seat: tuple[int, ...]
    br_unreachable_infosets_by_seat: tuple[int, ...]
    mean_abs_probability_update: float
    max_abs_probability_update: float


def _sample_gap_and_gradient(
    validator: MultiwayResponseValidator,
    *,
    br_stay: Sequence[bool],
    holes,
    turn: Card,
    river: Card,
) -> tuple[float, dict[int, float]]:
    """One chance-deal sample of aggregate deviation gap and its subgradient.

    The best-response actions are treated as fixed maximizers for this sample
    block (Danskin subgradient). For each target player i we evaluate the public
    tree with i using its learned BR and every other player using the current
    profile. A policy coordinate belonging to player k therefore receives the
    derivative of all BR_i terms for i != k, minus the derivative of the sum of
    current-profile utilities.

    Pot Fold has the useful property that every player acts at most once, so a
    behavioral coordinate is an independent two-action simplex coordinate. The
    returned gradient is with respect to P(STAY) at each dense exact infoset.
    """

    n = validator.num_players
    h = validator.hole_state_count
    nodes = validator.nodes
    node_count = len(nodes)
    if len(br_stay) != validator.expected_infosets:
        raise ValueError("BR action vector does not match exact infoset count")

    profile_values = [0.0] * (node_count * n)
    profile_p_stay = [0.0] * node_count
    profile_reach = [0.0] * node_count
    hole_ids, _ranks = validator._fill_profile(
        holes=holes,
        turn=turn,
        river=river,
        values=profile_values,
        p_stay_by_node=profile_p_stay,
    )
    validator._fill_reach(profile_p_stay, profile_reach)

    variant_values: list[list[float]] = []
    variant_reaches: list[list[float]] = []

    for target in range(n):
        values = [0.0] * node_count
        p_stay_by_node = [0.0] * node_count

        # Children are created before parents in _build_public_tree, so ascending
        # node order is a bottom-up value pass.
        for idx, node in enumerate(nodes):
            if node.terminal:
                values[idx] = profile_values[idx * n + target]
                continue

            assert node.actor is not None and node.public_id is not None
            assert node.fold_child is not None and node.stay_child is not None
            key = node.public_id * h + hole_ids[node.actor]
            if node.actor == target:
                p_stay = 1.0 if br_stay[key] else 0.0
            else:
                p_stay = validator.policy[key][1]
            p_stay_by_node[idx] = p_stay
            values[idx] = (
                (1.0 - p_stay) * values[node.fold_child]
                + p_stay * values[node.stay_child]
            )

        reach = [0.0] * node_count
        reach[validator.root] = 1.0
        # Parents have greater indices than children, so descending order is a
        # top-down reach pass.
        for idx in range(node_count - 1, -1, -1):
            node = nodes[idx]
            if node.terminal:
                continue
            assert node.fold_child is not None and node.stay_child is not None
            r = reach[idx]
            p_stay = p_stay_by_node[idx]
            reach[node.fold_child] += r * (1.0 - p_stay)
            reach[node.stay_child] += r * p_stay

        variant_values.append(values)
        variant_reaches.append(reach)

    root = validator.root
    profile_sum = sum(profile_values[root * n + p] for p in range(n))
    gap = sum(variant_values[p][root] for p in range(n)) - profile_sum

    gradient: dict[int, float] = {}
    for idx, node in enumerate(nodes):
        if node.terminal:
            continue
        assert node.actor is not None and node.public_id is not None
        assert node.fold_child is not None and node.stay_child is not None
        actor = node.actor
        key = node.public_id * h + hole_ids[actor]

        # - d/dsigma_actor sum_i u_i(sigma)
        profile_child_delta_sum = 0.0
        for player in range(n):
            profile_child_delta_sum += (
                profile_values[node.stay_child * n + player]
                - profile_values[node.fold_child * n + player]
            )
        g = -profile_reach[idx] * profile_child_delta_sum

        # + d/dsigma_actor sum_{i != actor} u_i(BR_i, sigma_-i).
        # The i == actor term does not depend on sigma_actor because that
        # player's complete behavior is replaced by BR_i.
        for target in range(n):
            if target == actor:
                continue
            g += variant_reaches[target][idx] * (
                variant_values[target][node.stay_child]
                - variant_values[target][node.fold_child]
            )

        gradient[key] = gradient.get(key, 0.0) + g

    return gap, gradient


def estimate_gap_gradient(
    validator: MultiwayResponseValidator,
    *,
    br_stay: Sequence[bool],
    samples: int,
) -> tuple[list[float], PEDGradientEstimate]:
    """Monte-Carlo estimate of the PED aggregate-deviation subgradient."""

    if samples <= 0:
        raise ValueError("samples must be positive")
    gradient = [0.0] * validator.expected_infosets
    gap_sum = 0.0

    for _ in range(samples):
        holes, turn, river = validator._sample()
        gap, sample_gradient = _sample_gap_and_gradient(
            validator,
            br_stay=br_stay,
            holes=holes,
            turn=turn,
            river=river,
        )
        gap_sum += gap
        for key, value in sample_gradient.items():
            gradient[key] += value

    inv = 1.0 / samples
    gradient = [g * inv for g in gradient]
    abs_gradient = [abs(g) for g in gradient]
    report = PEDGradientEstimate(
        samples=samples,
        mean_sample_gap=gap_sum * inv,
        max_abs_gradient=max(abs_gradient, default=0.0),
        mean_abs_gradient=(sum(abs_gradient) / len(abs_gradient)) if abs_gradient else 0.0,
        nonzero_gradient_infosets=sum(1 for g in gradient if g != 0.0),
    )
    return gradient, report


def refine_policy_ped(
    *,
    num_players: int,
    flop,
    initial_policy: dict[int, tuple[float, float]],
    rake_pct: float,
    rake_cap: float | None,
    rounds: int = 32,
    br_samples_per_round: int = 50_000,
    gradient_samples_per_round: int = 50_000,
    initial_max_coordinate_step: float = 0.10,
    seed_base: int = 9_502_026,
) -> tuple[dict[int, tuple[float, float]], list[PEDRound]]:
    """Finite stochastic Projected Exploitability Descent for Pot Fold.

    The objective is the sum of unilateral deviation gains. Each round first
    learns one pure BR for every seat against the current policy, then estimates
    a stochastic subgradient on an independent chance block and takes a
    normalized projected subgradient step. The L-infinity normalization makes
    the largest coordinate movement exactly `initial_max_coordinate_step /
    sqrt(round)` before projection. Projection is local clipping because every
    Pot-Fold player acts at most once and each exact infoset is a two-action
    simplex.
    """

    if not 3 <= num_players <= 8:
        raise ValueError("multiway PED requires 3..8 players")
    if rounds <= 0:
        raise ValueError("rounds must be positive")
    if br_samples_per_round <= 0 or gradient_samples_per_round <= 0:
        raise ValueError("per-round sample counts must be positive")
    if initial_max_coordinate_step <= 0.0:
        raise ValueError("initial_max_coordinate_step must be positive")

    policy = dict(initial_policy)
    audit: list[PEDRound] = []

    for round_index in range(1, rounds + 1):
        br_seed = seed_base + round_index
        gradient_seed = seed_base + 10_000 + round_index

        br_validator = MultiwayResponseValidator(
            num_players=num_players,
            flop=flop,
            policy=policy,
            rake_pct=rake_pct,
            rake_cap=rake_cap,
            seed=br_seed,
        )
        br_stay, br_stay_counts, br_unreachable = _learn_pure_best_responses(
            br_validator,
            samples=br_samples_per_round,
        )

        gradient_validator = MultiwayResponseValidator(
            num_players=num_players,
            flop=flop,
            policy=policy,
            rake_pct=rake_pct,
            rake_cap=rake_cap,
            seed=gradient_seed,
        )
        gradient, gradient_report = estimate_gap_gradient(
            gradient_validator,
            br_stay=br_stay,
            samples=gradient_samples_per_round,
        )

        radius = initial_max_coordinate_step / math.sqrt(round_index)
        max_abs_gradient = gradient_report.max_abs_gradient
        scale = (radius / max_abs_gradient) if max_abs_gradient > 0.0 else 0.0

        next_policy: dict[int, tuple[float, float]] = {}
        deltas: list[float] = []
        for key in range(gradient_validator.expected_infosets):
            old_stay = policy[key][1]
            new_stay = old_stay - scale * gradient[key]
            new_stay = min(1.0, max(0.0, new_stay))
            next_policy[key] = (1.0 - new_stay, new_stay)
            deltas.append(abs(new_stay - old_stay))

        policy = next_policy
        audit.append(
            PEDRound(
                round_index=round_index,
                br_seed=br_seed,
                gradient_seed=gradient_seed,
                br_samples=br_samples_per_round,
                gradient_samples=gradient_samples_per_round,
                max_coordinate_step=radius,
                gradient=gradient_report,
                br_stay_states_by_seat=br_stay_counts,
                br_unreachable_infosets_by_seat=br_unreachable,
                mean_abs_probability_update=(sum(deltas) / len(deltas)) if deltas else 0.0,
                max_abs_probability_update=max(deltas, default=0.0),
            )
        )

    return policy, audit


def main() -> None:
    ap = argparse.ArgumentParser(description="Finite exact-state multiway FP-PED refinement")
    ap.add_argument("--players", type=int, required=True)
    ap.add_argument("--policy", required=True)
    ap.add_argument("--flop", required=True)
    ap.add_argument("--rake-pct", type=float, default=0.02)
    ap.add_argument("--rake-cap", type=float, default=None)
    ap.add_argument("--rounds", type=int, default=32)
    ap.add_argument("--br-samples-per-round", type=int, required=True)
    ap.add_argument("--gradient-samples-per-round", type=int, required=True)
    ap.add_argument("--initial-max-coordinate-step", type=float, default=0.10)
    ap.add_argument("--seed-base", type=int, default=9502026)
    ap.add_argument("--out-policy", required=True)
    ap.add_argument("--out-audit", required=True)
    args = ap.parse_args()

    flop = parse_flop(args.flop)
    initial = load_policy_csv(args.policy)
    refined, rounds = refine_policy_ped(
        num_players=args.players,
        flop=flop,
        initial_policy=initial,
        rake_pct=args.rake_pct,
        rake_cap=args.rake_cap,
        rounds=args.rounds,
        br_samples_per_round=args.br_samples_per_round,
        gradient_samples_per_round=args.gradient_samples_per_round,
        initial_max_coordinate_step=args.initial_max_coordinate_step,
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
        "ped_version": MULTIWAY_PED_VERSION,
        "num_players": args.players,
        "flop": [str(card) for card in flop],
        "rounds": args.rounds,
        "br_samples_per_round": args.br_samples_per_round,
        "gradient_samples_per_round": args.gradient_samples_per_round,
        "initial_max_coordinate_step": args.initial_max_coordinate_step,
        "step_schedule": "0.10/sqrt(round) normalized L_inf subgradient",
        "seed_base": args.seed_base,
        "rake_pct": args.rake_pct,
        "rake_cap": args.rake_cap,
        "strategic_card_abstraction": "none",
        "exact_symmetry_reduction": "global_suit_isomorphism_only",
        "method": "finite_sampled_projected_exploitability_descent",
        "round_audit": [asdict(round_) for round_ in rounds],
    }
    Path(args.out_audit).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
