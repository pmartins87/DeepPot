from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path

from .hu_response import HUResponseValidator, load_policy_csv, parse_flop

REFINER_VERSION = "2026-09-07.1"


@dataclass(frozen=True)
class RefinementRound:
    round_index: int
    seed: int
    samples: int
    alpha: float
    player0_br_stay_states: int
    player1_br_stay_states: int
    player0_unlearned_states: int
    player1_unreached_states: int
    mean_abs_probability_update: float
    max_abs_probability_update: float


def _learn_pure_best_responses(
    validator: HUResponseValidator,
    *,
    samples: int,
) -> tuple[list[bool], list[bool], int, int]:
    if samples <= 0:
        raise ValueError("samples must be positive")

    h = validator.hole_state_count
    p0_s_sum = [0.0] * h
    p0_count = [0] * h
    p1_s_weighted_sum = [0.0] * h
    p1_reach_weight = [0.0] * h

    for _ in range(samples):
        h0, h1, turn, river = validator._sample()
        id0 = validator._raw_hole_to_state_id[h0]
        id1 = validator._raw_hole_to_state_id[h1]
        p0_stay = validator._p_stay(0, id0)
        p1_stay = validator._p_stay(1, id1)
        u_ss = validator._showdown_utility(h0, h1, turn, river)

        p0_s_value = (
            (1.0 - p1_stay) * validator._u_p0_stay_p1_fold[0]
            + p1_stay * u_ss[0]
        )
        p0_s_sum[id0] += p0_s_value
        p0_count[id0] += 1

        if p0_stay > 0.0:
            p1_s_weighted_sum[id1] += p0_stay * u_ss[1]
            p1_reach_weight[id1] += p0_stay

    p0_fold_value = validator._u_p0_fold[0]
    p1_fold_value = validator._u_p0_stay_p1_fold[1]
    p0_br = [False] * h
    p1_br = [False] * h
    p0_unlearned = 0
    p1_unreached = 0

    for hole_id in range(h):
        if p0_count[hole_id] > 0:
            p0_br[hole_id] = (p0_s_sum[hole_id] / p0_count[hole_id]) > p0_fold_value
        else:
            p0_unlearned += 1
            p0_br[hole_id] = validator._p_stay(0, hole_id) >= 0.5

        if p1_reach_weight[hole_id] > 0.0:
            p1_br[hole_id] = (
                p1_s_weighted_sum[hole_id] / p1_reach_weight[hole_id]
            ) > p1_fold_value
        else:
            p1_unreached += 1
            p1_br[hole_id] = validator._p_stay(1, hole_id) >= 0.5

    return p0_br, p1_br, p0_unlearned, p1_unreached


def refine_policy(
    *,
    flop,
    initial_policy: dict[int, tuple[float, float]],
    rake_pct: float,
    rake_cap: float | None,
    rounds: int = 12,
    samples_per_round: int = 100_000,
    prior_weight: int = 4,
    seed_base: int = 920_2026,
) -> tuple[dict[int, tuple[float, float]], list[RefinementRound]]:
    """One finite damped-response correction to an exact HU policy.

    This is the single solver-method correction allowed by the Base-v1 roadmap
    after the initial A72r CFR consensus failed the HU response gate. It is a
    finite sampled fictitious-response refinement, not an open-ended tuning loop.

    Each round learns one pure unilateral best response for each player against
    the CURRENT opponent policy, then moves the current behavioral strategy a
    diminishing amount toward that response:

        alpha_t = 1 / (prior_weight + t)

    The initial CFR consensus therefore acts as `prior_weight` pseudo-iterations.
    Default schedule is fixed at 12 rounds, 100k chance samples per round and
    prior_weight=4 (alpha 0.20 down to 0.0625). No card-state abstraction occurs.
    """

    if rounds <= 0:
        raise ValueError("rounds must be positive")
    if samples_per_round <= 0:
        raise ValueError("samples_per_round must be positive")
    if prior_weight <= 0:
        raise ValueError("prior_weight must be positive")

    policy = dict(initial_policy)
    audit: list[RefinementRound] = []

    for round_index in range(1, rounds + 1):
        seed = seed_base + round_index
        validator = HUResponseValidator(
            flop=flop,
            policy=policy,
            rake_pct=rake_pct,
            rake_cap=rake_cap,
            seed=seed,
        )
        p0_br, p1_br, p0_unlearned, p1_unreached = _learn_pure_best_responses(
            validator,
            samples=samples_per_round,
        )
        h = validator.hole_state_count
        alpha = 1.0 / (prior_weight + round_index)
        deltas: list[float] = []
        next_policy: dict[int, tuple[float, float]] = {}

        for public_id, br in ((0, p0_br), (1, p1_br)):
            for hole_id in range(h):
                key = public_id * h + hole_id
                old_stay = policy[key][1]
                target = 1.0 if br[hole_id] else 0.0
                new_stay = (1.0 - alpha) * old_stay + alpha * target
                # Guard only against floating-point drift; this is not clipping
                # strategic information or discretizing the policy.
                new_stay = min(1.0, max(0.0, new_stay))
                next_policy[key] = (1.0 - new_stay, new_stay)
                deltas.append(abs(new_stay - old_stay))

        policy = next_policy
        audit.append(
            RefinementRound(
                round_index=round_index,
                seed=seed,
                samples=samples_per_round,
                alpha=alpha,
                player0_br_stay_states=sum(p0_br),
                player1_br_stay_states=sum(p1_br),
                player0_unlearned_states=p0_unlearned,
                player1_unreached_states=p1_unreached,
                mean_abs_probability_update=(sum(deltas) / len(deltas)) if deltas else 0.0,
                max_abs_probability_update=max(deltas, default=0.0),
            )
        )

    return policy, audit


def write_policy_csv(path: str | Path, policy: dict[int, tuple[float, float]], hole_state_count: int) -> None:
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
    ap = argparse.ArgumentParser(description="Finite exact-HU damped response refinement")
    ap.add_argument("--policy", required=True)
    ap.add_argument("--flop", default="Ah 7d 2c")
    ap.add_argument("--rake-pct", type=float, default=0.02)
    ap.add_argument("--rake-cap", type=float, default=None)
    ap.add_argument("--rounds", type=int, default=12)
    ap.add_argument("--samples-per-round", type=int, default=100000)
    ap.add_argument("--prior-weight", type=int, default=4)
    ap.add_argument("--seed-base", type=int, default=9202026)
    ap.add_argument("--out-policy", required=True)
    ap.add_argument("--out-audit", required=True)
    args = ap.parse_args()

    flop = parse_flop(args.flop)
    initial = load_policy_csv(args.policy)
    refined, rounds = refine_policy(
        flop=flop,
        initial_policy=initial,
        rake_pct=args.rake_pct,
        rake_cap=args.rake_cap,
        rounds=args.rounds,
        samples_per_round=args.samples_per_round,
        prior_weight=args.prior_weight,
        seed_base=args.seed_base,
    )
    validator = HUResponseValidator(
        flop=flop,
        policy=refined,
        rake_pct=args.rake_pct,
        rake_cap=args.rake_cap,
        seed=args.seed_base,
    )
    write_policy_csv(args.out_policy, refined, validator.hole_state_count)
    payload = {
        "refiner_version": REFINER_VERSION,
        "flop": [str(card) for card in flop],
        "rounds": args.rounds,
        "samples_per_round": args.samples_per_round,
        "prior_weight": args.prior_weight,
        "seed_base": args.seed_base,
        "rake_pct": args.rake_pct,
        "rake_cap": args.rake_cap,
        "strategic_card_abstraction": "none",
        "round_audit": [round_.__dict__ for round_ in rounds],
    }
    Path(args.out_audit).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
