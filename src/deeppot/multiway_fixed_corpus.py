from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

from .cards import Card
from .multiway_refine import write_policy_csv
from .multiway_response import MultiwayResponseValidator, load_policy_csv, parse_flop
from .multiway_worst_seat import _project_policy_step, _sample_seat_gaps_and_gradients

MULTIWAY_FIXED_CORPUS_VERSION = "2026-09-07.1"

ChanceDeal = tuple[tuple[tuple[Card, Card], ...], Card, Card]


@dataclass(frozen=True)
class FixedCorpusStage:
    samples: int
    seat_gaps: tuple[float, ...]
    seat_weights: tuple[float, ...]
    br_stay_states_by_seat: tuple[int, ...]
    unreachable_infosets_by_seat: tuple[int, ...]
    max_abs_gradient_by_seat: tuple[float, ...]
    mean_abs_gradient_by_seat: tuple[float, ...]
    negative_gap_count: int


@dataclass(frozen=True)
class FixedCorpusRound:
    round_index: int
    max_coordinate_radius: float
    predictor: FixedCorpusStage
    corrector: FixedCorpusStage
    predictor_mean_abs_probability_update: float
    predictor_max_abs_probability_update: float
    corrector_mean_abs_probability_update: float
    corrector_max_abs_probability_update: float


def build_fixed_corpus(
    validator: MultiwayResponseValidator,
    *,
    samples: int,
) -> tuple[ChanceDeal, ...]:
    """Materialize one immutable chance corpus from the validator RNG.

    P4G deliberately reuses these exact deals on every optimization round.
    This removes the round-to-round sign drift seen when a best response learned
    on one random block is evaluated on a different random block. The final P4
    release gate remains an independent split-sample validator, so the corpus
    is an optimization device, not the acceptance sample.
    """

    if samples <= 0:
        raise ValueError("samples must be positive")
    return tuple(validator._sample() for _ in range(samples))


def corpus_sha256(corpus: Sequence[ChanceDeal]) -> str:
    digest = hashlib.sha256()
    for holes, turn, river in corpus:
        for hole in holes:
            for card in hole:
                digest.update(str(card).encode("ascii"))
                digest.update(b",")
            digest.update(b"|")
        digest.update(str(turn).encode("ascii"))
        digest.update(b",")
        digest.update(str(river).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _learn_pure_best_responses_on_corpus(
    validator: MultiwayResponseValidator,
    corpus: Sequence[ChanceDeal],
) -> tuple[list[bool], tuple[int, ...], tuple[int, ...]]:
    """Learn exact-in-corpus pure unilateral BRs for every seat.

    The same fixed deals are used for reach weighting and both child values.
    Since every Pot-Fold player acts at most once, maximizing independently at
    each reached information set is the empirical unilateral best response for
    this finite chance corpus.
    """

    if not corpus:
        raise ValueError("corpus must not be empty")

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


def _smooth_worst_seat_weights(
    seat_gaps: Sequence[float],
    *,
    beta: float,
) -> tuple[float, ...]:
    """Softmax weights for a deterministic smooth approximation to max-seat gap."""

    if not seat_gaps:
        raise ValueError("seat_gaps must not be empty")
    if beta <= 0.0:
        raise ValueError("beta must be positive")

    # Same-corpus empirical BR gains should be non-negative. Clip microscopic
    # floating error rather than allowing a negative estimate to attract or
    # repel optimization weight.
    effective = [max(0.0, float(gap)) for gap in seat_gaps]
    peak = max(effective)
    raw = [math.exp(beta * (gap - peak)) for gap in effective]
    total = sum(raw)
    if total <= 0.0 or not math.isfinite(total):
        raise FloatingPointError("invalid smooth-max normalization")
    return tuple(value / total for value in raw)


def _weighted_gradient(
    gradients: Sequence[Sequence[float]],
    weights: Sequence[float],
) -> list[float]:
    if len(gradients) != len(weights) or not gradients:
        raise ValueError("one non-empty gradient vector is required per seat weight")
    width = len(gradients[0])
    if any(len(row) != width for row in gradients):
        raise ValueError("gradient vectors must share one width")
    return [
        sum(weights[seat] * gradients[seat][key] for seat in range(len(weights)))
        for key in range(width)
    ]


def _estimate_fixed_stage(
    *,
    num_players: int,
    flop,
    policy: dict[int, tuple[float, float]],
    rake_pct: float,
    rake_cap: float | None,
    corpus: Sequence[ChanceDeal],
    smoothmax_beta: float,
) -> tuple[tuple[list[float], ...], FixedCorpusStage]:
    validator = MultiwayResponseValidator(
        num_players=num_players,
        flop=flop,
        policy=policy,
        rake_pct=rake_pct,
        rake_cap=rake_cap,
        seed=1,
    )
    br_stay, stay_counts, unreachable = _learn_pure_best_responses_on_corpus(
        validator,
        corpus,
    )

    n = validator.num_players
    expected = validator.expected_infosets
    gap_sums = [0.0] * n
    gradients = [[0.0] * expected for _ in range(n)]

    for holes, turn, river in corpus:
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

    inv = 1.0 / len(corpus)
    seat_gaps = tuple(value * inv for value in gap_sums)
    max_abs: list[float] = []
    mean_abs: list[float] = []
    for seat in range(n):
        gradients[seat] = [value * inv for value in gradients[seat]]
        abs_values = [abs(value) for value in gradients[seat]]
        max_abs.append(max(abs_values, default=0.0))
        mean_abs.append((sum(abs_values) / len(abs_values)) if abs_values else 0.0)

    weights = _smooth_worst_seat_weights(seat_gaps, beta=smoothmax_beta)
    report = FixedCorpusStage(
        samples=len(corpus),
        seat_gaps=seat_gaps,
        seat_weights=weights,
        br_stay_states_by_seat=stay_counts,
        unreachable_infosets_by_seat=unreachable,
        max_abs_gradient_by_seat=tuple(max_abs),
        mean_abs_gradient_by_seat=tuple(mean_abs),
        negative_gap_count=sum(1 for value in seat_gaps if value < -1e-10),
    )
    return tuple(gradients), report


def refine_policy_fixed_corpus(
    *,
    num_players: int,
    flop,
    initial_policy: dict[int, tuple[float, float]],
    rake_pct: float,
    rake_cap: float | None,
    rounds: int = 32,
    corpus_samples: int = 50_000,
    corpus_seed: int = 9_802_026,
    initial_max_coordinate_radius: float = 0.05,
    smoothmax_beta: float = 100.0,
) -> tuple[dict[int, tuple[float, float]], str, list[FixedCorpusRound]]:
    """P4G deterministic fixed-corpus smooth worst-seat mirror-prox.

    One immutable chance corpus is generated before optimization. Every BR,
    seat-gap and gradient estimate in all predictor/corrector rounds reuses that
    corpus. Thus the empirical objective is deterministic and a BR evaluated on
    the same corpus cannot acquire the stochastic negative-gap pathology that
    blocked P4F. The final acceptance test must still use the independent P4
    split-sample response validator.
    """

    if not 3 <= num_players <= 8:
        raise ValueError("P4G requires 3..8 players")
    if rounds <= 0:
        raise ValueError("rounds must be positive")
    if corpus_samples <= 0:
        raise ValueError("corpus_samples must be positive")
    if initial_max_coordinate_radius <= 0.0:
        raise ValueError("initial_max_coordinate_radius must be positive")
    if smoothmax_beta <= 0.0:
        raise ValueError("smoothmax_beta must be positive")

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
    audit: list[FixedCorpusRound] = []

    for round_index in range(1, rounds + 1):
        radius = initial_max_coordinate_radius / math.sqrt(round_index)

        predictor_gradients, predictor_report = _estimate_fixed_stage(
            num_players=num_players,
            flop=flop,
            policy=policy,
            rake_pct=rake_pct,
            rake_cap=rake_cap,
            corpus=corpus,
            smoothmax_beta=smoothmax_beta,
        )
        predictor_gradient = _weighted_gradient(
            predictor_gradients,
            predictor_report.seat_weights,
        )
        predictor_policy, predictor_mean_update, predictor_max_update = _project_policy_step(
            policy,
            predictor_gradient,
            radius,
        )

        corrector_gradients, corrector_report = _estimate_fixed_stage(
            num_players=num_players,
            flop=flop,
            policy=predictor_policy,
            rake_pct=rake_pct,
            rake_cap=rake_cap,
            corpus=corpus,
            smoothmax_beta=smoothmax_beta,
        )
        corrector_gradient = _weighted_gradient(
            corrector_gradients,
            corrector_report.seat_weights,
        )
        next_policy, corrector_mean_update, corrector_max_update = _project_policy_step(
            policy,
            corrector_gradient,
            radius,
        )

        audit.append(
            FixedCorpusRound(
                round_index=round_index,
                max_coordinate_radius=radius,
                predictor=predictor_report,
                corrector=corrector_report,
                predictor_mean_abs_probability_update=predictor_mean_update,
                predictor_max_abs_probability_update=predictor_max_update,
                corrector_mean_abs_probability_update=corrector_mean_update,
                corrector_max_abs_probability_update=corrector_max_update,
            )
        )
        policy = next_policy

    return policy, corpus_hash, audit


def main() -> None:
    ap = argparse.ArgumentParser(
        description="P4G deterministic exact-state fixed-corpus worst-seat mirror-prox"
    )
    ap.add_argument("--players", type=int, required=True)
    ap.add_argument("--policy", required=True)
    ap.add_argument("--flop", required=True)
    ap.add_argument("--rake-pct", type=float, default=0.02)
    ap.add_argument("--rake-cap", type=float, default=None)
    ap.add_argument("--rounds", type=int, default=32)
    ap.add_argument("--corpus-samples", type=int, default=50_000)
    ap.add_argument("--corpus-seed", type=int, default=9802026)
    ap.add_argument("--initial-max-coordinate-radius", type=float, default=0.05)
    ap.add_argument("--smoothmax-beta", type=float, default=100.0)
    ap.add_argument("--out-policy", required=True)
    ap.add_argument("--out-audit", required=True)
    args = ap.parse_args()

    flop = parse_flop(args.flop)
    initial = load_policy_csv(args.policy)
    refined, corpus_hash, rounds = refine_policy_fixed_corpus(
        num_players=args.players,
        flop=flop,
        initial_policy=initial,
        rake_pct=args.rake_pct,
        rake_cap=args.rake_cap,
        rounds=args.rounds,
        corpus_samples=args.corpus_samples,
        corpus_seed=args.corpus_seed,
        initial_max_coordinate_radius=args.initial_max_coordinate_radius,
        smoothmax_beta=args.smoothmax_beta,
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
        "fixed_corpus_version": MULTIWAY_FIXED_CORPUS_VERSION,
        "num_players": args.players,
        "flop": [str(card) for card in flop],
        "rounds": args.rounds,
        "corpus_samples": args.corpus_samples,
        "corpus_seed": args.corpus_seed,
        "corpus_sha256": corpus_hash,
        "initial_max_coordinate_radius": args.initial_max_coordinate_radius,
        "radius_schedule": "initial/sqrt(round)",
        "smoothmax_beta": args.smoothmax_beta,
        "rake_pct": args.rake_pct,
        "rake_cap": args.rake_cap,
        "strategic_card_abstraction": "none",
        "exact_symmetry_reduction": "global_suit_isomorphism_only",
        "method": "deterministic_fixed_corpus_smooth_worst_seat_mirror_prox",
        "round_audit": [asdict(round_) for round_ in rounds],
    }
    Path(args.out_audit).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
