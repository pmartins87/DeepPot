from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

from .multiway_fixed_corpus import ChanceDeal, build_fixed_corpus, corpus_sha256
from .multiway_refine import write_policy_csv
from .multiway_response import MultiwayResponseValidator, load_policy_csv, parse_flop

MULTIWAY_LOGIT_CONTINUATION_VERSION = "2026-09-07.1"


@dataclass(frozen=True)
class TargetAdvantageEstimate:
    seat: int
    samples: int
    reachable_infosets: int
    unreachable_infosets: int
    max_abs_advantage: float
    mean_abs_advantage: float


@dataclass(frozen=True)
class LogitSeatUpdate:
    temperature_index: int
    temperature: float
    sweep_index: int
    seat: int
    damping: float
    advantage: TargetAdvantageEstimate
    mean_abs_probability_update: float
    max_abs_probability_update: float


def _estimate_target_advantages_on_corpus(
    validator: MultiwayResponseValidator,
    corpus: Sequence[ChanceDeal],
    *,
    target_seat: int,
) -> tuple[list[float], list[bool], TargetAdvantageEstimate]:
    """Conditional STAY-FOLD advantages for one seat on one immutable corpus.

    Pot Fold gives each player at most one decision per hand. Therefore the
    reach probability of a node controlled by target_seat contains only chance
    and opponent-policy factors. Conditioning the two child values by that
    reach gives the player's exact-in-corpus local best-response operator.
    """

    if not corpus:
        raise ValueError("corpus must not be empty")
    if not 0 <= target_seat < validator.num_players:
        raise ValueError("target_seat out of range")

    n = validator.num_players
    h = validator.hole_state_count
    expected = validator.expected_infosets
    node_count = len(validator.nodes)

    values = [0.0] * (node_count * n)
    p_stay_by_node = [0.0] * node_count
    reach = [0.0] * node_count
    weight_sum = [0.0] * expected
    weighted_delta_sum = [0.0] * expected

    for holes, turn, river in corpus:
        hole_ids, _ = validator._fill_profile(
            holes=holes,
            turn=turn,
            river=river,
            values=values,
            p_stay_by_node=p_stay_by_node,
        )
        validator._fill_reach(p_stay_by_node, reach)

        for idx, node in enumerate(validator.nodes):
            if node.terminal or node.actor != target_seat:
                continue
            assert node.public_id is not None
            assert node.fold_child is not None and node.stay_child is not None
            r = reach[idx]
            if r <= 0.0:
                continue
            key = node.public_id * h + hole_ids[target_seat]
            delta = (
                values[node.stay_child * n + target_seat]
                - values[node.fold_child * n + target_seat]
            )
            weight_sum[key] += r
            weighted_delta_sum[key] += r * delta

    advantages = [0.0] * expected
    reachable = [False] * expected
    abs_values: list[float] = []
    reachable_count = 0
    seat_infosets = 0
    for key in range(expected):
        public_id, _ = divmod(key, h)
        if validator.actor_by_public[public_id] != target_seat:
            continue
        seat_infosets += 1
        w = weight_sum[key]
        if w <= 0.0:
            continue
        value = weighted_delta_sum[key] / w
        advantages[key] = value
        reachable[key] = True
        reachable_count += 1
        abs_values.append(abs(value))

    return advantages, reachable, TargetAdvantageEstimate(
        seat=target_seat,
        samples=len(corpus),
        reachable_infosets=reachable_count,
        unreachable_infosets=seat_infosets - reachable_count,
        max_abs_advantage=max(abs_values, default=0.0),
        mean_abs_advantage=(sum(abs_values) / len(abs_values)) if abs_values else 0.0,
    )


def _logistic(x: float) -> float:
    if x >= 40.0:
        return 1.0
    if x <= -40.0:
        return 0.0
    return 1.0 / (1.0 + math.exp(-x))


def _apply_target_logit_update(
    validator: MultiwayResponseValidator,
    policy: dict[int, tuple[float, float]],
    advantages: Sequence[float],
    reachable: Sequence[bool],
    *,
    target_seat: int,
    temperature: float,
    damping: float,
) -> tuple[dict[int, tuple[float, float]], float, float]:
    if temperature <= 0.0:
        raise ValueError("temperature must be positive")
    if not 0.0 < damping <= 1.0:
        raise ValueError("damping must lie in (0, 1]")
    if len(advantages) != validator.expected_infosets or len(reachable) != validator.expected_infosets:
        raise ValueError("advantage/reach vectors do not match policy width")

    h = validator.hole_state_count
    out = dict(policy)
    deltas: list[float] = []
    for key in range(validator.expected_infosets):
        public_id, _ = divmod(key, h)
        if validator.actor_by_public[public_id] != target_seat or not reachable[key]:
            continue
        old_stay = policy[key][1]
        target_stay = _logistic(advantages[key] / temperature)
        new_stay = (1.0 - damping) * old_stay + damping * target_stay
        new_stay = min(1.0, max(0.0, new_stay))
        out[key] = (1.0 - new_stay, new_stay)
        deltas.append(abs(new_stay - old_stay))

    return (
        out,
        (sum(deltas) / len(deltas)) if deltas else 0.0,
        max(deltas, default=0.0),
    )


def refine_policy_cyclic_logit_continuation(
    *,
    num_players: int,
    flop,
    initial_policy: dict[int, tuple[float, float]],
    rake_pct: float,
    rake_cap: float | None,
    temperatures: Sequence[float] = (0.16, 0.08, 0.04, 0.02),
    sweeps_per_temperature: int = 12,
    damping: float = 0.50,
    corpus_samples: int = 50_000,
    corpus_seed: int = 9_902_026,
) -> tuple[dict[int, tuple[float, float]], str, list[LogitSeatUpdate]]:
    """P4H deterministic cyclic logit-response homotopy.

    This is a fixed-point method, not an exploitability-gradient method. At each
    temperature, seats are updated in reverse action order (BTN to first actor).
    Each seat is moved halfway toward its empirical logit best response while
    all later updates see the already-updated policy. The temperature is then
    reduced on a frozen continuation path toward a near-pure best response.

    The chance corpus is immutable throughout P4H. Final acceptance remains the
    independent split-sample unilateral-response gate, not the training corpus.
    """

    if not 3 <= num_players <= 8:
        raise ValueError("P4H requires 3..8 players")
    if not temperatures or any(t <= 0.0 for t in temperatures):
        raise ValueError("temperatures must be non-empty and positive")
    if any(temperatures[i + 1] >= temperatures[i] for i in range(len(temperatures) - 1)):
        raise ValueError("temperatures must be strictly decreasing")
    if sweeps_per_temperature <= 0:
        raise ValueError("sweeps_per_temperature must be positive")
    if not 0.0 < damping <= 1.0:
        raise ValueError("damping must lie in (0, 1]")
    if corpus_samples <= 0:
        raise ValueError("corpus_samples must be positive")

    corpus_validator = MultiwayResponseValidator(
        num_players=num_players,
        flop=flop,
        policy=initial_policy,
        rake_pct=rake_pct,
        rake_cap=rake_cap,
        seed=corpus_seed,
    )
    corpus = build_fixed_corpus(corpus_validator, samples=corpus_samples)
    corpus_hash = corpus_sha256(corpus)

    policy = dict(initial_policy)
    audit: list[LogitSeatUpdate] = []
    seat_order = tuple(range(num_players - 1, -1, -1))

    for temperature_index, temperature in enumerate(temperatures, start=1):
        for sweep_index in range(1, sweeps_per_temperature + 1):
            for seat in seat_order:
                validator = MultiwayResponseValidator(
                    num_players=num_players,
                    flop=flop,
                    policy=policy,
                    rake_pct=rake_pct,
                    rake_cap=rake_cap,
                    seed=1,
                )
                advantages, reachable, report = _estimate_target_advantages_on_corpus(
                    validator,
                    corpus,
                    target_seat=seat,
                )
                policy, mean_update, max_update = _apply_target_logit_update(
                    validator,
                    policy,
                    advantages,
                    reachable,
                    target_seat=seat,
                    temperature=temperature,
                    damping=damping,
                )
                audit.append(
                    LogitSeatUpdate(
                        temperature_index=temperature_index,
                        temperature=temperature,
                        sweep_index=sweep_index,
                        seat=seat,
                        damping=damping,
                        advantage=report,
                        mean_abs_probability_update=mean_update,
                        max_abs_probability_update=max_update,
                    )
                )

    return policy, corpus_hash, audit


def main() -> None:
    ap = argparse.ArgumentParser(description="P4H cyclic fixed-corpus logit-response continuation")
    ap.add_argument("--players", type=int, required=True)
    ap.add_argument("--policy", required=True)
    ap.add_argument("--flop", required=True)
    ap.add_argument("--rake-pct", type=float, default=0.02)
    ap.add_argument("--rake-cap", type=float, default=None)
    ap.add_argument("--temperatures", default="0.16,0.08,0.04,0.02")
    ap.add_argument("--sweeps-per-temperature", type=int, default=12)
    ap.add_argument("--damping", type=float, default=0.50)
    ap.add_argument("--corpus-samples", type=int, default=50_000)
    ap.add_argument("--corpus-seed", type=int, default=9902026)
    ap.add_argument("--out-policy", required=True)
    ap.add_argument("--out-audit", required=True)
    args = ap.parse_args()

    temperatures = tuple(float(x.strip()) for x in args.temperatures.split(",") if x.strip())
    flop = parse_flop(args.flop)
    initial = load_policy_csv(args.policy)
    refined, corpus_hash, updates = refine_policy_cyclic_logit_continuation(
        num_players=args.players,
        flop=flop,
        initial_policy=initial,
        rake_pct=args.rake_pct,
        rake_cap=args.rake_cap,
        temperatures=temperatures,
        sweeps_per_temperature=args.sweeps_per_temperature,
        damping=args.damping,
        corpus_samples=args.corpus_samples,
        corpus_seed=args.corpus_seed,
    )
    validator = MultiwayResponseValidator(
        num_players=args.players,
        flop=flop,
        policy=refined,
        rake_pct=args.rake_pct,
        rake_cap=args.rake_cap,
        seed=args.corpus_seed,
    )
    write_policy_csv(args.out_policy, refined, validator.hole_state_count)
    payload = {
        "logit_continuation_version": MULTIWAY_LOGIT_CONTINUATION_VERSION,
        "num_players": args.players,
        "flop": [str(card) for card in flop],
        "temperatures": list(temperatures),
        "sweeps_per_temperature": args.sweeps_per_temperature,
        "seat_order": "reverse_action_order_BTN_to_first_actor",
        "damping": args.damping,
        "corpus_samples": args.corpus_samples,
        "corpus_seed": args.corpus_seed,
        "corpus_sha256": corpus_hash,
        "final_temperature_log2_bound_if_fixed_point": temperatures[-1] * math.log(2.0),
        "rake_pct": args.rake_pct,
        "rake_cap": args.rake_cap,
        "strategic_card_abstraction": "none",
        "exact_symmetry_reduction": "global_suit_isomorphism_only",
        "method": "deterministic_cyclic_logit_response_continuation",
        "update_audit": [asdict(update) for update in updates],
    }
    Path(args.out_audit).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
