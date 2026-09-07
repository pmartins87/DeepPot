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

MULTIWAY_WORST_SEAT_VERSION = "2026-09-07.1"


@dataclass(frozen=True)
class SeatGapGradientEstimate:
    samples: int
    seat_gaps: tuple[float, ...]
    max_abs_gradient_by_seat: tuple[float, ...]
    mean_abs_gradient_by_seat: tuple[float, ...]


@dataclass(frozen=True)
class WorstSeatRound:
    round_index: int
    predictor_br_seed: int
    predictor_gradient_seed: int
    corrector_br_seed: int
    corrector_gradient_seed: int
    br_samples_per_stage: int
    gradient_samples_per_stage: int
    primal_radius: float
    dual_radius: float
    seat_weights_before: tuple[float, ...]
    predictor_seat_gaps: tuple[float, ...]
    predictor_seat_weights: tuple[float, ...]
    corrector_seat_gaps: tuple[float, ...]
    seat_weights_after: tuple[float, ...]
    predictor_br_stay_states_by_seat: tuple[int, ...]
    predictor_unreachable_infosets_by_seat: tuple[int, ...]
    corrector_br_stay_states_by_seat: tuple[int, ...]
    corrector_unreachable_infosets_by_seat: tuple[int, ...]
    predictor_mean_abs_probability_update: float
    predictor_max_abs_probability_update: float
    corrector_mean_abs_probability_update: float
    corrector_max_abs_probability_update: float


def _sample_seat_gaps_and_gradients(
    validator: MultiwayResponseValidator,
    *,
    br_stay: Sequence[bool],
    holes,
    turn: Card,
    river: Card,
) -> tuple[tuple[float, ...], tuple[dict[int, float], ...]]:
    """Evaluate one chance deal for every seat-specific deviation objective.

    For seat i the objective is

        E_i(sigma) = u_i(BR_i(sigma_-i), sigma_-i) - u_i(sigma).

    The BR action vector is held fixed for this sampled derivative block (the
    same Danskin convention used by P4D). Because every player acts at most once
    in Pot Fold, a behavioral coordinate does not affect the reach probability
    of its own information set. This makes the child-value derivative exact for
    the fixed sampled deal.
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

        # Children precede parents in the frozen public-tree representation.
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
    seat_gaps = tuple(
        variant_values[target][root] - profile_values[root * n + target]
        for target in range(n)
    )

    gradients: list[dict[int, float]] = [dict() for _ in range(n)]
    for idx, node in enumerate(nodes):
        if node.terminal:
            continue
        assert node.actor is not None and node.public_id is not None
        assert node.fold_child is not None and node.stay_child is not None
        actor = node.actor
        key = node.public_id * h + hole_ids[actor]

        for target in range(n):
            profile_delta = (
                profile_values[node.stay_child * n + target]
                - profile_values[node.fold_child * n + target]
            )
            g = -profile_reach[idx] * profile_delta

            # BR_target replaces target's complete behavior, so E_target's BR
            # term does not depend on target's own policy coordinates.
            if actor != target:
                variant_delta = (
                    variant_values[target][node.stay_child]
                    - variant_values[target][node.fold_child]
                )
                g += variant_reaches[target][idx] * variant_delta

            gradients[target][key] = gradients[target].get(key, 0.0) + g

    return seat_gaps, tuple(gradients)


def estimate_seat_gaps_and_gradients(
    validator: MultiwayResponseValidator,
    *,
    br_stay: Sequence[bool],
    samples: int,
) -> tuple[tuple[list[float], ...], SeatGapGradientEstimate]:
    """Monte-Carlo estimate of all E_i values and their policy gradients."""

    if samples <= 0:
        raise ValueError("samples must be positive")

    n = validator.num_players
    expected = validator.expected_infosets
    gap_sums = [0.0] * n
    gradients = [[0.0] * expected for _ in range(n)]

    for _ in range(samples):
        holes, turn, river = validator._sample()
        gaps, sample_gradients = _sample_seat_gaps_and_gradients(
            validator,
            br_stay=br_stay,
            holes=holes,
            turn=turn,
            river=river,
        )
        for seat in range(n):
            gap_sums[seat] += gaps[seat]
            dense = gradients[seat]
            for key, value in sample_gradients[seat].items():
                dense[key] += value

    inv = 1.0 / samples
    seat_gaps = tuple(value * inv for value in gap_sums)
    max_abs: list[float] = []
    mean_abs: list[float] = []
    for seat in range(n):
        gradients[seat] = [value * inv for value in gradients[seat]]
        abs_values = [abs(value) for value in gradients[seat]]
        max_abs.append(max(abs_values, default=0.0))
        mean_abs.append((sum(abs_values) / len(abs_values)) if abs_values else 0.0)

    return tuple(gradients), SeatGapGradientEstimate(
        samples=samples,
        seat_gaps=seat_gaps,
        max_abs_gradient_by_seat=tuple(max_abs),
        mean_abs_gradient_by_seat=tuple(mean_abs),
    )


def _weighted_gradient(
    gradients: Sequence[Sequence[float]],
    seat_weights: Sequence[float],
) -> list[float]:
    if len(gradients) != len(seat_weights):
        raise ValueError("one gradient vector is required per seat weight")
    if not gradients:
        return []
    width = len(gradients[0])
    if any(len(row) != width for row in gradients):
        raise ValueError("gradient vectors must share one width")
    return [
        sum(seat_weights[seat] * gradients[seat][key] for seat in range(len(seat_weights)))
        for key in range(width)
    ]


def _project_policy_step(
    policy: dict[int, tuple[float, float]],
    gradient: Sequence[float],
    radius: float,
) -> tuple[dict[int, tuple[float, float]], float, float]:
    if radius <= 0.0:
        raise ValueError("radius must be positive")
    if len(gradient) != len(policy):
        raise ValueError("gradient width must equal policy size")

    max_abs_gradient = max((abs(value) for value in gradient), default=0.0)
    scale = radius / max_abs_gradient if max_abs_gradient > 0.0 else 0.0
    next_policy: dict[int, tuple[float, float]] = {}
    deltas: list[float] = []
    for key in range(len(policy)):
        old_stay = policy[key][1]
        new_stay = old_stay - scale * gradient[key]
        new_stay = min(1.0, max(0.0, new_stay))
        next_policy[key] = (1.0 - new_stay, new_stay)
        deltas.append(abs(new_stay - old_stay))
    return (
        next_policy,
        (sum(deltas) / len(deltas)) if deltas else 0.0,
        max(deltas, default=0.0),
    )


def _dual_exponentiated_step(
    seat_weights: Sequence[float],
    seat_gaps: Sequence[float],
    radius: float,
) -> tuple[float, ...]:
    """Mirror-ascent step on the seat simplex for max_i E_i."""

    if len(seat_weights) != len(seat_gaps) or not seat_weights:
        raise ValueError("seat weights and gaps must have the same non-zero length")
    if radius <= 0.0:
        raise ValueError("radius must be positive")
    if any(weight <= 0.0 for weight in seat_weights):
        raise ValueError("dual weights must be strictly positive")

    weighted_mean = sum(w * g for w, g in zip(seat_weights, seat_gaps))
    centered = [gap - weighted_mean for gap in seat_gaps]
    max_abs = max((abs(value) for value in centered), default=0.0)
    scale = radius / max_abs if max_abs > 0.0 else 0.0

    log_values = [math.log(weight) + scale * value for weight, value in zip(seat_weights, centered)]
    shift = max(log_values)
    raw = [math.exp(value - shift) for value in log_values]
    total = sum(raw)
    if total <= 0.0 or not math.isfinite(total):
        raise FloatingPointError("invalid dual normalization")
    return tuple(value / total for value in raw)


def _estimate_stage(
    *,
    num_players: int,
    flop,
    policy: dict[int, tuple[float, float]],
    rake_pct: float,
    rake_cap: float | None,
    br_seed: int,
    gradient_seed: int,
    br_samples: int,
    gradient_samples: int,
):
    br_validator = MultiwayResponseValidator(
        num_players=num_players,
        flop=flop,
        policy=policy,
        rake_pct=rake_pct,
        rake_cap=rake_cap,
        seed=br_seed,
    )
    br_stay, stay_counts, unreachable = _learn_pure_best_responses(
        br_validator,
        samples=br_samples,
    )
    gradient_validator = MultiwayResponseValidator(
        num_players=num_players,
        flop=flop,
        policy=policy,
        rake_pct=rake_pct,
        rake_cap=rake_cap,
        seed=gradient_seed,
    )
    gradients, report = estimate_seat_gaps_and_gradients(
        gradient_validator,
        br_stay=br_stay,
        samples=gradient_samples,
    )
    return gradients, report, stay_counts, unreachable


def refine_policy_primal_dual_worst_seat(
    *,
    num_players: int,
    flop,
    initial_policy: dict[int, tuple[float, float]],
    rake_pct: float,
    rake_cap: float | None,
    rounds: int = 32,
    br_samples_per_stage: int = 50_000,
    gradient_samples_per_stage: int = 50_000,
    initial_primal_radius: float = 0.05,
    initial_dual_radius: float = 0.50,
    seed_base: int = 9_702_026,
) -> tuple[dict[int, tuple[float, float]], tuple[float, ...], list[WorstSeatRound]]:
    """Finite primal-dual mirror-prox on max-seat unilateral exploitability."""

    if not 3 <= num_players <= 8:
        raise ValueError("P4F requires 3..8 players")
    if rounds <= 0:
        raise ValueError("rounds must be positive")
    if br_samples_per_stage <= 0 or gradient_samples_per_stage <= 0:
        raise ValueError("sample counts must be positive")
    if initial_primal_radius <= 0.0 or initial_dual_radius <= 0.0:
        raise ValueError("initial radii must be positive")

    policy = dict(initial_policy)
    seat_weights = tuple(1.0 / num_players for _ in range(num_players))
    audit: list[WorstSeatRound] = []

    for round_index in range(1, rounds + 1):
        base = seed_base + round_index
        predictor_br_seed = base
        predictor_gradient_seed = seed_base + 10_000 + round_index
        corrector_br_seed = seed_base + 20_000 + round_index
        corrector_gradient_seed = seed_base + 30_000 + round_index
        primal_radius = initial_primal_radius / math.sqrt(round_index)
        dual_radius = initial_dual_radius / math.sqrt(round_index)

        predictor_gradients, predictor_report, predictor_counts, predictor_unreachable = _estimate_stage(
            num_players=num_players,
            flop=flop,
            policy=policy,
            rake_pct=rake_pct,
            rake_cap=rake_cap,
            br_seed=predictor_br_seed,
            gradient_seed=predictor_gradient_seed,
            br_samples=br_samples_per_stage,
            gradient_samples=gradient_samples_per_stage,
        )
        predictor_weighted_gradient = _weighted_gradient(predictor_gradients, seat_weights)
        predictor_policy, predictor_mean_update, predictor_max_update = _project_policy_step(
            policy,
            predictor_weighted_gradient,
            primal_radius,
        )
        predictor_weights = _dual_exponentiated_step(
            seat_weights,
            predictor_report.seat_gaps,
            dual_radius,
        )

        corrector_gradients, corrector_report, corrector_counts, corrector_unreachable = _estimate_stage(
            num_players=num_players,
            flop=flop,
            policy=predictor_policy,
            rake_pct=rake_pct,
            rake_cap=rake_cap,
            br_seed=corrector_br_seed,
            gradient_seed=corrector_gradient_seed,
            br_samples=br_samples_per_stage,
            gradient_samples=gradient_samples_per_stage,
        )
        corrector_weighted_gradient = _weighted_gradient(corrector_gradients, predictor_weights)
        next_policy, corrector_mean_update, corrector_max_update = _project_policy_step(
            policy,
            corrector_weighted_gradient,
            primal_radius,
        )
        next_weights = _dual_exponentiated_step(
            seat_weights,
            corrector_report.seat_gaps,
            dual_radius,
        )

        audit.append(
            WorstSeatRound(
                round_index=round_index,
                predictor_br_seed=predictor_br_seed,
                predictor_gradient_seed=predictor_gradient_seed,
                corrector_br_seed=corrector_br_seed,
                corrector_gradient_seed=corrector_gradient_seed,
                br_samples_per_stage=br_samples_per_stage,
                gradient_samples_per_stage=gradient_samples_per_stage,
                primal_radius=primal_radius,
                dual_radius=dual_radius,
                seat_weights_before=seat_weights,
                predictor_seat_gaps=predictor_report.seat_gaps,
                predictor_seat_weights=predictor_weights,
                corrector_seat_gaps=corrector_report.seat_gaps,
                seat_weights_after=next_weights,
                predictor_br_stay_states_by_seat=predictor_counts,
                predictor_unreachable_infosets_by_seat=predictor_unreachable,
                corrector_br_stay_states_by_seat=corrector_counts,
                corrector_unreachable_infosets_by_seat=corrector_unreachable,
                predictor_mean_abs_probability_update=predictor_mean_update,
                predictor_max_abs_probability_update=predictor_max_update,
                corrector_mean_abs_probability_update=corrector_mean_update,
                corrector_max_abs_probability_update=corrector_max_update,
            )
        )
        policy = next_policy
        seat_weights = next_weights

    return policy, seat_weights, audit


def main() -> None:
    ap = argparse.ArgumentParser(description="P4F exact-state primal-dual worst-seat refinement")
    ap.add_argument("--players", type=int, required=True)
    ap.add_argument("--policy", required=True)
    ap.add_argument("--flop", required=True)
    ap.add_argument("--rake-pct", type=float, default=0.02)
    ap.add_argument("--rake-cap", type=float, default=None)
    ap.add_argument("--rounds", type=int, default=32)
    ap.add_argument("--br-samples-per-stage", type=int, required=True)
    ap.add_argument("--gradient-samples-per-stage", type=int, required=True)
    ap.add_argument("--initial-primal-radius", type=float, default=0.05)
    ap.add_argument("--initial-dual-radius", type=float, default=0.50)
    ap.add_argument("--seed-base", type=int, default=9702026)
    ap.add_argument("--out-policy", required=True)
    ap.add_argument("--out-audit", required=True)
    args = ap.parse_args()

    flop = parse_flop(args.flop)
    initial = load_policy_csv(args.policy)
    refined, seat_weights, rounds = refine_policy_primal_dual_worst_seat(
        num_players=args.players,
        flop=flop,
        initial_policy=initial,
        rake_pct=args.rake_pct,
        rake_cap=args.rake_cap,
        rounds=args.rounds,
        br_samples_per_stage=args.br_samples_per_stage,
        gradient_samples_per_stage=args.gradient_samples_per_stage,
        initial_primal_radius=args.initial_primal_radius,
        initial_dual_radius=args.initial_dual_radius,
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
        "worst_seat_version": MULTIWAY_WORST_SEAT_VERSION,
        "num_players": args.players,
        "flop": [str(card) for card in flop],
        "rounds": args.rounds,
        "br_samples_per_stage": args.br_samples_per_stage,
        "gradient_samples_per_stage": args.gradient_samples_per_stage,
        "initial_primal_radius": args.initial_primal_radius,
        "primal_radius_schedule": "0.05/sqrt(round) normalized L_inf projected descent",
        "initial_dual_radius": args.initial_dual_radius,
        "dual_radius_schedule": "0.50/sqrt(round) centered normalized exponentiated ascent",
        "final_seat_weights": seat_weights,
        "seed_base": args.seed_base,
        "rake_pct": args.rake_pct,
        "rake_cap": args.rake_cap,
        "strategic_card_abstraction": "none",
        "exact_symmetry_reduction": "global_suit_isomorphism_only",
        "method": "finite_primal_dual_mirror_prox_worst_seat_exploitability",
        "round_audit": [asdict(round_) for round_ in rounds],
    }
    Path(args.out_audit).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
