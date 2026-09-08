from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping

from .multiway_response import MultiwayResponseValidator


COMPACT_AUDIT_VERSION = "2026-09-08.deepkk-parity.1"


@dataclass(frozen=True)
class CompactAuditResult:
    num_players: int
    hole_state_count: int
    public_scenarios: int
    expected_infosets: int
    final_stay_bits: bytes
    solver_stay_bits: bytes
    confident_bits: bytes
    low_coverage_bits: bytes
    summary: dict


def _set_bit(bits: bytearray, index: int) -> None:
    bits[index >> 3] |= 1 << (index & 7)


def bit_is_set(bits: bytes | bytearray, index: int) -> bool:
    return bool(bits[index >> 3] & (1 << (index & 7)))


def _weighted_stderr(
    sum_w: float,
    sum_w2: float,
    sum_gap: float,
    sum_gap2: float,
) -> tuple[float | None, float]:
    if sum_w <= 0.0 or sum_w2 <= 0.0:
        return None, 0.0
    mean = sum_gap / sum_w
    var = max(0.0, sum_gap2 / sum_w - mean * mean)
    n_eff = (sum_w * sum_w) / sum_w2
    if n_eff <= 1.0:
        return None, n_eff
    return math.sqrt(var / n_eff), n_eff


def evaluate_policy_deepkk_style_compact(
    *,
    num_players: int,
    flop,
    policy: Mapping[int, tuple[float, float]],
    samples: int,
    min_effective_visits: float,
    seed: int,
    rake_pct: float,
    rake_cap: float | None,
) -> CompactAuditResult:
    """DeepKK-style EV/CI audit without materializing hundreds of millions of CSV rows.

    The decision rule is intentionally the same one used by the DeepKK-style
    evaluator:

      * estimate EV(FOLD), EV(STAY), and the STAY-FOLD gap under the trained policy;
      * mark the EV-best action confident only when |gap| > CI95 and the minimum
        effective-visit threshold is met;
      * otherwise retain the greedy action of the solver's linear-average policy.

    The output is four dense bit vectors in exact infoset-key order. This changes
    storage only, not the mathematical decision rule.
    """

    if samples <= 0:
        raise ValueError("samples must be positive")
    if min_effective_visits < 0.0:
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
    sum_gap = [0.0] * expected
    sum_gap2 = [0.0] * expected

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
            gap = (
                values[node.stay_child * n + actor]
                - values[node.fold_child * n + actor]
            )
            sum_w[key] += r
            sum_w2[key] += r * r
            sum_gap[key] += r * gap
            sum_gap2[key] += r * gap * gap

    byte_count = (expected + 7) // 8
    final_bits = bytearray(byte_count)
    solver_bits = bytearray(byte_count)
    confident_bits = bytearray(byte_count)
    low_cov_bits = bytearray(byte_count)

    covered = 0
    confident = 0
    low_coverage = 0
    overrides = 0
    solver_stay_count = 0
    final_stay_count = 0

    for key in range(expected):
        w = sum_w[key]
        if w > 0.0:
            covered += 1
        gap = sum_gap[key] / w if w > 0.0 else 0.0
        stderr, n_eff = _weighted_stderr(w, sum_w2[key], sum_gap[key], sum_gap2[key])
        ci95 = None if stderr is None else 1.959963984540054 * stderr
        low_cov = n_eff < min_effective_visits
        is_confident = ci95 is not None and abs(gap) > ci95 and not low_cov

        solver_stay = float(policy[key][1]) >= 0.5
        ev_stay = gap > 0.0
        final_stay = ev_stay if is_confident else solver_stay

        if solver_stay:
            _set_bit(solver_bits, key)
            solver_stay_count += 1
        if final_stay:
            _set_bit(final_bits, key)
            final_stay_count += 1
        if is_confident:
            _set_bit(confident_bits, key)
            confident += 1
        if low_cov:
            _set_bit(low_cov_bits, key)
            low_coverage += 1
        if final_stay != solver_stay:
            overrides += 1

    summary = {
        "audit_version": COMPACT_AUDIT_VERSION,
        "samples": int(samples),
        "seed": int(seed),
        "total_infosets": int(expected),
        "covered_infosets": int(covered),
        "covered_infosets_pct": 100.0 * covered / max(1, expected),
        "low_coverage_infosets": int(low_coverage),
        "confident_best_action_infosets": int(confident),
        "confident_infosets_pct": 100.0 * confident / max(1, expected),
        "solver_stay_infosets": int(solver_stay_count),
        "final_stay_infosets": int(final_stay_count),
        "confident_ev_overrides": int(overrides),
        "decision_rule": "confident_EV_best_else_solver_average_greedy",
        "confidence_rule": "abs(EV_STAY-EV_FOLD)>CI95 and effective_visits>=minimum",
        "min_effective_visits": float(min_effective_visits),
        "strategic_card_abstraction": "none",
        "storage": "dense_little_endian_bit_vectors_in_exact_infoset_key_order",
    }

    return CompactAuditResult(
        num_players=num_players,
        hole_state_count=h,
        public_scenarios=validator.public_scenarios,
        expected_infosets=expected,
        final_stay_bits=bytes(final_bits),
        solver_stay_bits=bytes(solver_bits),
        confident_bits=bytes(confident_bits),
        low_coverage_bits=bytes(low_cov_bits),
        summary=summary,
    )
