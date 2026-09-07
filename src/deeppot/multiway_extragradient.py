from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

from .multiway_refine import write_policy_csv
from .multiway_response import MultiwayResponseValidator, load_policy_csv, parse_flop

MULTIWAY_EXTRAGRADIENT_VERSION = "2026-09-07.1"


@dataclass(frozen=True)
class AdvantageEstimate:
    samples: int
    reachable_infosets: int
    unreachable_infosets: int
    max_abs_advantage: float
    mean_abs_advantage: float


@dataclass(frozen=True)
class ExtraGradientRound:
    round_index: int
    predictor_seed: int
    corrector_seed: int
    predictor_samples: int
    corrector_samples: int
    max_coordinate_radius: float
    predictor: AdvantageEstimate
    corrector: AdvantageEstimate
    predictor_mean_abs_update: float
    predictor_max_abs_update: float
    corrector_mean_abs_update: float
    corrector_max_abs_update: float


def estimate_conditional_advantages(
    validator: MultiwayResponseValidator,
    *,
    samples: int,
) -> tuple[list[float], AdvantageEstimate]:
    """Estimate exact-infoset E[u(STAY)-u(FOLD) | infoset, opponents].

    Every Pot-Fold player acts at most once. Therefore the public reach of an
    actor's node contains only chance/opponent strategy factors; there is no
    earlier action by the same player to remove. Weighting child-value
    differences by that reach and conditioning by the accumulated reach gives
    the player's local Nash action-advantage operator at each dense exact
    infoset.
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
    weighted_delta_sum = [0.0] * expected

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
            delta = (
                values[node.stay_child * n + actor]
                - values[node.fold_child * n + actor]
            )
            weight_sum[key] += r
            weighted_delta_sum[key] += r * delta

    advantages = [0.0] * expected
    reachable = 0
    abs_values: list[float] = []
    for key in range(expected):
        w = weight_sum[key]
        if w > 0.0:
            advantages[key] = weighted_delta_sum[key] / w
            reachable += 1
            abs_values.append(abs(advantages[key]))

    report = AdvantageEstimate(
        samples=samples,
        reachable_infosets=reachable,
        unreachable_infosets=expected - reachable,
        max_abs_advantage=max(abs_values, default=0.0),
        mean_abs_advantage=(sum(abs_values) / len(abs_values)) if abs_values else 0.0,
    )
    return advantages, report


def _projected_step(
    policy: dict[int, tuple[float, float]],
    advantages: list[float],
    *,
    radius: float,
) -> tuple[dict[int, tuple[float, float]], float, float]:
    """Take one normalized Euclidean projected ascent step on own advantages."""

    if radius <= 0.0:
        raise ValueError("radius must be positive")
    if len(advantages) != len(policy):
        raise ValueError("advantage vector does not match policy")

    max_abs = max((abs(x) for x in advantages), default=0.0)
    scale = radius / max_abs if max_abs > 0.0 else 0.0
    out: dict[int, tuple[float, float]] = {}
    deltas: list[float] = []
    for key in range(len(advantages)):
        old_stay = policy[key][1]
        new_stay = old_stay + scale * advantages[key]
        new_stay = min(1.0, max(0.0, new_stay))
        out[key] = (1.0 - new_stay, new_stay)
        deltas.append(abs(new_stay - old_stay))
    return (
        out,
        (sum(deltas) / len(deltas)) if deltas else 0.0,
        max(deltas, default=0.0),
    )


def refine_policy_extragradient(
    *,
    num_players: int,
    flop,
    initial_policy: dict[int, tuple[float, float]],
    rake_pct: float,
    rake_cap: float | None,
    rounds: int = 64,
    predictor_samples_per_round: int = 50_000,
    corrector_samples_per_round: int = 50_000,
    initial_max_coordinate_radius: float = 0.10,
    seed_base: int = 9_602_026,
) -> tuple[dict[int, tuple[float, float]], list[ExtraGradientRound]]:
    """Finite exact-state projected extragradient on the Nash operator.

    At round t:
      1. estimate every player's conditional STAY-vs-FOLD advantage at p_t;
      2. construct predictor q_t by projected ascent from p_t;
      3. independently estimate the same Nash operator at q_t;
      4. correct from p_t (not q_t) using the predictor-point operator.

    The maximum coordinate radius is frozen to 0.10/sqrt(t). No external gate
    metric participates in the updates or chooses an intermediate checkpoint.
    """

    if not 3 <= num_players <= 8:
        raise ValueError("multiway extragradient requires 3..8 players")
    if rounds <= 0:
        raise ValueError("rounds must be positive")
    if predictor_samples_per_round <= 0 or corrector_samples_per_round <= 0:
        raise ValueError("per-round sample counts must be positive")
    if initial_max_coordinate_radius <= 0.0:
        raise ValueError("initial_max_coordinate_radius must be positive")

    policy = dict(initial_policy)
    audit: list[ExtraGradientRound] = []

    for round_index in range(1, rounds + 1):
        predictor_seed = seed_base + round_index
        corrector_seed = seed_base + 10_000 + round_index
        radius = initial_max_coordinate_radius / math.sqrt(round_index)

        predictor_validator = MultiwayResponseValidator(
            num_players=num_players,
            flop=flop,
            policy=policy,
            rake_pct=rake_pct,
            rake_cap=rake_cap,
            seed=predictor_seed,
        )
        predictor_adv, predictor_report = estimate_conditional_advantages(
            predictor_validator,
            samples=predictor_samples_per_round,
        )
        predictor_policy, predictor_mean, predictor_max = _projected_step(
            policy,
            predictor_adv,
            radius=radius,
        )

        corrector_validator = MultiwayResponseValidator(
            num_players=num_players,
            flop=flop,
            policy=predictor_policy,
            rake_pct=rake_pct,
            rake_cap=rake_cap,
            seed=corrector_seed,
        )
        corrector_adv, corrector_report = estimate_conditional_advantages(
            corrector_validator,
            samples=corrector_samples_per_round,
        )
        next_policy, corrector_mean, corrector_max = _projected_step(
            policy,
            corrector_adv,
            radius=radius,
        )

        policy = next_policy
        audit.append(
            ExtraGradientRound(
                round_index=round_index,
                predictor_seed=predictor_seed,
                corrector_seed=corrector_seed,
                predictor_samples=predictor_samples_per_round,
                corrector_samples=corrector_samples_per_round,
                max_coordinate_radius=radius,
                predictor=predictor_report,
                corrector=corrector_report,
                predictor_mean_abs_update=predictor_mean,
                predictor_max_abs_update=predictor_max,
                corrector_mean_abs_update=corrector_mean,
                corrector_max_abs_update=corrector_max,
            )
        )

    return policy, audit


def main() -> None:
    ap = argparse.ArgumentParser(description="Finite exact-state projected Nash extragradient")
    ap.add_argument("--players", type=int, required=True)
    ap.add_argument("--policy", required=True)
    ap.add_argument("--flop", required=True)
    ap.add_argument("--rake-pct", type=float, default=0.02)
    ap.add_argument("--rake-cap", type=float, default=None)
    ap.add_argument("--rounds", type=int, default=64)
    ap.add_argument("--predictor-samples-per-round", type=int, required=True)
    ap.add_argument("--corrector-samples-per-round", type=int, required=True)
    ap.add_argument("--initial-max-coordinate-radius", type=float, default=0.10)
    ap.add_argument("--seed-base", type=int, default=9602026)
    ap.add_argument("--out-policy", required=True)
    ap.add_argument("--out-audit", required=True)
    args = ap.parse_args()

    flop = parse_flop(args.flop)
    initial = load_policy_csv(args.policy)
    refined, rounds = refine_policy_extragradient(
        num_players=args.players,
        flop=flop,
        initial_policy=initial,
        rake_pct=args.rake_pct,
        rake_cap=args.rake_cap,
        rounds=args.rounds,
        predictor_samples_per_round=args.predictor_samples_per_round,
        corrector_samples_per_round=args.corrector_samples_per_round,
        initial_max_coordinate_radius=args.initial_max_coordinate_radius,
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
        "extragradient_version": MULTIWAY_EXTRAGRADIENT_VERSION,
        "num_players": args.players,
        "flop": [str(card) for card in flop],
        "rounds": args.rounds,
        "predictor_samples_per_round": args.predictor_samples_per_round,
        "corrector_samples_per_round": args.corrector_samples_per_round,
        "initial_max_coordinate_radius": args.initial_max_coordinate_radius,
        "radius_schedule": "0.10/sqrt(round) normalized L_inf projected extragradient",
        "seed_base": args.seed_base,
        "rake_pct": args.rake_pct,
        "rake_cap": args.rake_cap,
        "strategic_card_abstraction": "none",
        "exact_symmetry_reduction": "global_suit_isomorphism_only",
        "method": "finite_sampled_projected_nash_extragradient",
        "round_audit": [asdict(round_) for round_ in rounds],
    }
    Path(args.out_audit).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
