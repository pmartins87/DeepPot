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

MULTIWAY_ANDERSON_QRE_VERSION = "2026-09-07.1"


@dataclass(frozen=True)
class AndersonIteration:
    temperature_index: int
    temperature: float
    iteration_index: int
    memory_used: int
    anderson_mix: float
    residual_max_abs: float
    residual_mean_abs: float
    reachable_infosets: int
    unreachable_infosets: int
    mean_abs_probability_update: float
    max_abs_probability_update: float
    linear_solve_fallback: bool


def _logistic(x: float) -> float:
    if x >= 40.0:
        return 1.0
    if x <= -40.0:
        return 0.0
    return 1.0 / (1.0 + math.exp(-x))


def _estimate_all_advantages_on_corpus(
    validator: MultiwayResponseValidator,
    corpus: Sequence[ChanceDeal],
) -> tuple[list[float], list[bool]]:
    """Estimate every exact-infoset STAY-FOLD advantage in one corpus pass.

    P4H recomputed a full corpus pass separately for each seat. P4I evaluates
    the same mathematical operator for all seats simultaneously. Because every
    Pot-Fold player acts at most once, the node reach before that player's
    decision contains only chance and opponent-strategy factors, so the
    reach-conditioned child-value difference is the correct local response
    operator for that infoset.
    """

    if not corpus:
        raise ValueError("corpus must not be empty")

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
            if node.terminal:
                continue
            assert node.actor is not None and node.public_id is not None
            assert node.fold_child is not None and node.stay_child is not None
            r = reach[idx]
            if r <= 0.0:
                continue
            actor = node.actor
            key = node.public_id * h + hole_ids[actor]
            delta = (
                values[node.stay_child * n + actor]
                - values[node.fold_child * n + actor]
            )
            weight_sum[key] += r
            weighted_delta_sum[key] += r * delta

    advantages = [0.0] * expected
    reachable = [False] * expected
    for key in range(expected):
        w = weight_sum[key]
        if w > 0.0:
            advantages[key] = weighted_delta_sum[key] / w
            reachable[key] = True
    return advantages, reachable


def _policy_to_vector(policy: dict[int, tuple[float, float]]) -> list[float]:
    return [policy[key][1] for key in range(len(policy))]


def _vector_to_policy(vector: Sequence[float]) -> dict[int, tuple[float, float]]:
    out: dict[int, tuple[float, float]] = {}
    for key, value in enumerate(vector):
        p_stay = min(1.0, max(0.0, float(value)))
        out[key] = (1.0 - p_stay, p_stay)
    return out


def _fixed_point_operator(
    *,
    num_players: int,
    flop,
    vector: Sequence[float],
    rake_pct: float,
    rake_cap: float | None,
    corpus: Sequence[ChanceDeal],
    temperature: float,
) -> tuple[list[float], list[float], list[bool]]:
    if temperature <= 0.0:
        raise ValueError("temperature must be positive")
    policy = _vector_to_policy(vector)
    validator = MultiwayResponseValidator(
        num_players=num_players,
        flop=flop,
        policy=policy,
        rake_pct=rake_pct,
        rake_cap=rake_cap,
        seed=1,
    )
    advantages, reachable = _estimate_all_advantages_on_corpus(validator, corpus)
    target = list(vector)
    residual = [0.0] * len(vector)
    for key, is_reachable in enumerate(reachable):
        if not is_reachable:
            continue
        target[key] = _logistic(advantages[key] / temperature)
        residual[key] = target[key] - vector[key]
    return target, residual, reachable


def _solve_small_system(matrix: list[list[float]], rhs: list[float]) -> list[float] | None:
    """Deterministic Gaussian elimination with pivoting for tiny Anderson systems."""

    n = len(rhs)
    if len(matrix) != n or any(len(row) != n for row in matrix):
        raise ValueError("matrix must be square and match rhs")
    a = [list(row) + [rhs[i]] for i, row in enumerate(matrix)]

    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < 1e-18 or not math.isfinite(a[pivot][col]):
            return None
        if pivot != col:
            a[col], a[pivot] = a[pivot], a[col]
        denom = a[col][col]
        for j in range(col, n + 1):
            a[col][j] /= denom
        for row in range(n):
            if row == col:
                continue
            factor = a[row][col]
            if factor == 0.0:
                continue
            for j in range(col, n + 1):
                a[row][j] -= factor * a[col][j]

    solution = [a[i][n] for i in range(n)]
    if any(not math.isfinite(x) for x in solution):
        return None
    return solution


def _anderson_candidate(
    xs: Sequence[Sequence[float]],
    fs: Sequence[Sequence[float]],
    target: Sequence[float],
    reachable: Sequence[bool],
    *,
    memory: int,
    ridge: float,
    mix: float,
) -> tuple[list[float], int, bool]:
    """Type-II Anderson candidate blended with the ordinary Picard target.

    `xs[-1]` and `fs[-1]` are the current iterate and residual. The accelerated
    point is `g_k - (dX+dF) gamma`, where gamma solves the regularized least
    squares problem `min ||f_k-dF gamma||^2`. Projection to the behavioral
    simplex is coordinate-wise clipping because every infoset has two actions.
    """

    if memory < 0:
        raise ValueError("memory must be non-negative")
    if ridge < 0.0:
        raise ValueError("ridge must be non-negative")
    if not 0.0 <= mix <= 1.0:
        raise ValueError("mix must lie in [0,1]")
    if not xs or len(xs) != len(fs):
        raise ValueError("x/f histories must be non-empty and aligned")

    current = list(xs[-1])
    picard = list(target)
    width = len(current)
    if len(picard) != width or len(reachable) != width:
        raise ValueError("vector widths do not match")

    m = min(memory, len(xs) - 1)
    if m <= 0:
        return picard, 0, False

    start = len(xs) - 1 - m
    d_x: list[list[float]] = []
    d_f: list[list[float]] = []
    for j in range(start, len(xs) - 1):
        d_x.append([xs[j + 1][k] - xs[j][k] for k in range(width)])
        d_f.append([fs[j + 1][k] - fs[j][k] for k in range(width)])

    f_current = fs[-1]
    gram = [[0.0] * m for _ in range(m)]
    rhs = [0.0] * m
    for i in range(m):
        rhs[i] = sum(d_f[i][k] * f_current[k] for k in range(width))
        for j in range(i, m):
            value = sum(d_f[i][k] * d_f[j][k] for k in range(width))
            gram[i][j] = value
            gram[j][i] = value
        gram[i][i] += ridge

    gamma = _solve_small_system(gram, rhs)
    if gamma is None:
        return picard, m, True

    accelerated = list(picard)
    for j in range(m):
        coeff = gamma[j]
        dx = d_x[j]
        df = d_f[j]
        for k in range(width):
            accelerated[k] -= coeff * (dx[k] + df[k])

    candidate = [0.0] * width
    for k in range(width):
        if not reachable[k]:
            candidate[k] = current[k]
            continue
        value = (1.0 - mix) * picard[k] + mix * accelerated[k]
        candidate[k] = min(1.0, max(0.0, value))
    return candidate, m, False


def refine_policy_anderson_qre(
    *,
    num_players: int,
    flop,
    initial_policy: dict[int, tuple[float, float]],
    rake_pct: float,
    rake_cap: float | None,
    temperatures: Sequence[float] = (0.16, 0.08, 0.04, 0.02),
    iterations_per_temperature: int = 12,
    memory: int = 5,
    ridge: float = 1e-8,
    anderson_mix: float = 0.50,
    corpus_samples: int = 50_000,
    corpus_seed: int = 9_912_026,
) -> tuple[dict[int, tuple[float, float]], str, list[AndersonIteration]]:
    """P4I deterministic Anderson-accelerated QRE continuation.

    P4H's cyclic Gauss-Seidel logit updates were still moving by large amounts
    after the frozen final sweep, so P4I changes the numerical fixed-point
    solver rather than adding P4H sweeps. At each temperature it forms the
    simultaneous logit-response operator for every exact infoset and applies a
    regularized Type-II Anderson step, blended 50/50 with the ordinary Picard
    target and projected to [0,1]. Exactly the frozen number of iterations is
    executed; residuals are diagnostic only and never select a checkpoint.
    """

    if not 3 <= num_players <= 8:
        raise ValueError("P4I requires 3..8 players")
    if not temperatures or any(t <= 0.0 for t in temperatures):
        raise ValueError("temperatures must be non-empty and positive")
    if any(temperatures[i + 1] >= temperatures[i] for i in range(len(temperatures) - 1)):
        raise ValueError("temperatures must be strictly decreasing")
    if iterations_per_temperature <= 0:
        raise ValueError("iterations_per_temperature must be positive")
    if memory < 0:
        raise ValueError("memory must be non-negative")
    if ridge < 0.0:
        raise ValueError("ridge must be non-negative")
    if not 0.0 <= anderson_mix <= 1.0:
        raise ValueError("anderson_mix must lie in [0,1]")
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

    vector = _policy_to_vector(initial_policy)
    audit: list[AndersonIteration] = []

    for temperature_index, temperature in enumerate(temperatures, start=1):
        xs: list[list[float]] = []
        fs: list[list[float]] = []
        for iteration_index in range(1, iterations_per_temperature + 1):
            target, residual, reachable = _fixed_point_operator(
                num_players=num_players,
                flop=flop,
                vector=vector,
                rake_pct=rake_pct,
                rake_cap=rake_cap,
                corpus=corpus,
                temperature=temperature,
            )
            xs.append(list(vector))
            fs.append(residual)
            keep = memory + 1
            if len(xs) > keep:
                xs.pop(0)
                fs.pop(0)

            next_vector, memory_used, fallback = _anderson_candidate(
                xs,
                fs,
                target,
                reachable,
                memory=memory,
                ridge=ridge,
                mix=anderson_mix,
            )
            abs_residual = [abs(residual[k]) for k, r in enumerate(reachable) if r]
            deltas = [abs(next_vector[k] - vector[k]) for k in range(len(vector))]
            audit.append(
                AndersonIteration(
                    temperature_index=temperature_index,
                    temperature=temperature,
                    iteration_index=iteration_index,
                    memory_used=memory_used,
                    anderson_mix=anderson_mix,
                    residual_max_abs=max(abs_residual, default=0.0),
                    residual_mean_abs=(sum(abs_residual) / len(abs_residual)) if abs_residual else 0.0,
                    reachable_infosets=sum(reachable),
                    unreachable_infosets=len(reachable) - sum(reachable),
                    mean_abs_probability_update=(sum(deltas) / len(deltas)) if deltas else 0.0,
                    max_abs_probability_update=max(deltas, default=0.0),
                    linear_solve_fallback=fallback,
                )
            )
            vector = next_vector

    return _vector_to_policy(vector), corpus_hash, audit


def main() -> None:
    ap = argparse.ArgumentParser(description="P4I Anderson-accelerated fixed-corpus QRE continuation")
    ap.add_argument("--players", type=int, required=True)
    ap.add_argument("--policy", required=True)
    ap.add_argument("--flop", required=True)
    ap.add_argument("--rake-pct", type=float, default=0.02)
    ap.add_argument("--rake-cap", type=float, default=None)
    ap.add_argument("--temperatures", default="0.16,0.08,0.04,0.02")
    ap.add_argument("--iterations-per-temperature", type=int, default=12)
    ap.add_argument("--memory", type=int, default=5)
    ap.add_argument("--ridge", type=float, default=1e-8)
    ap.add_argument("--anderson-mix", type=float, default=0.50)
    ap.add_argument("--corpus-samples", type=int, default=50_000)
    ap.add_argument("--corpus-seed", type=int, default=9912026)
    ap.add_argument("--out-policy", required=True)
    ap.add_argument("--out-audit", required=True)
    args = ap.parse_args()

    temperatures = tuple(float(x.strip()) for x in args.temperatures.split(",") if x.strip())
    flop = parse_flop(args.flop)
    initial = load_policy_csv(args.policy)
    refined, corpus_hash, audit = refine_policy_anderson_qre(
        num_players=args.players,
        flop=flop,
        initial_policy=initial,
        rake_pct=args.rake_pct,
        rake_cap=args.rake_cap,
        temperatures=temperatures,
        iterations_per_temperature=args.iterations_per_temperature,
        memory=args.memory,
        ridge=args.ridge,
        anderson_mix=args.anderson_mix,
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
        "anderson_qre_version": MULTIWAY_ANDERSON_QRE_VERSION,
        "num_players": args.players,
        "flop": [str(card) for card in flop],
        "temperatures": list(temperatures),
        "iterations_per_temperature": args.iterations_per_temperature,
        "memory": args.memory,
        "ridge": args.ridge,
        "anderson_mix": args.anderson_mix,
        "corpus_samples": args.corpus_samples,
        "corpus_seed": args.corpus_seed,
        "corpus_sha256": corpus_hash,
        "final_temperature_log2_bound_if_fixed_point": temperatures[-1] * math.log(2.0),
        "rake_pct": args.rake_pct,
        "rake_cap": args.rake_cap,
        "strategic_card_abstraction": "none",
        "exact_symmetry_reduction": "global_suit_isomorphism_only",
        "method": "deterministic_simultaneous_logit_qre_anderson_type2",
        "residual_use": "diagnostic_only_no_early_stop_no_checkpoint_selection",
        "iteration_audit": [asdict(item) for item in audit],
    }
    Path(args.out_audit).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
