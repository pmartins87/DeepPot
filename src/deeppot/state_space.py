from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

# Conjugacy classes of S4: cycle lengths -> number of permutations.
S4_CYCLE_TYPES: tuple[tuple[tuple[int, ...], int], ...] = (
    ((1, 1, 1, 1), 1),
    ((2, 1, 1), 6),
    ((2, 2), 3),
    ((3, 1), 8),
    ((4,), 6),
)


@dataclass(frozen=True)
class ExactStateSpaceSummary:
    canonical_flops: int
    naive_169_flop_states: int
    exact_flop_hole_orbits: int
    exact_vs_169_ratio: float


def _local_rank_assignment_counts(cycle_lengths: Iterable[int], board_cards: int, hole_cards: int) -> dict[tuple[int, int], int]:
    """Count invariant B/H/unused assignments for one rank.

    Under a fixed suit permutation, every suit-cycle must be assigned as a whole
    to board, hole, or unused. The returned map is keyed by the number of board
    and hole cards selected at this rank.
    """

    dp: dict[tuple[int, int], int] = {(0, 0): 1}
    for cycle_len in cycle_lengths:
        nxt: dict[tuple[int, int], int] = defaultdict(int)
        for (b, h), count in dp.items():
            nxt[(b, h)] += count
            if b + cycle_len <= board_cards:
                nxt[(b + cycle_len, h)] += count
            if h + cycle_len <= hole_cards:
                nxt[(b, h + cycle_len)] += count
        dp = dict(nxt)
    return dp


def fixed_partitioned_states(
    cycle_lengths: tuple[int, ...],
    *,
    ranks: int = 13,
    board_cards: int = 3,
    hole_cards: int = 2,
) -> int:
    """Number of exact (board subset, hole subset) states fixed by a suit permutation.

    Board and hole cards are unordered internally, disjoint, and retain their
    separate public/private roles. Only suit labels are considered symmetric.
    """

    local = _local_rank_assignment_counts(cycle_lengths, board_cards, hole_cards)
    total: dict[tuple[int, int], int] = {(0, 0): 1}
    for _ in range(ranks):
        nxt: dict[tuple[int, int], int] = defaultdict(int)
        for (b0, h0), c0 in total.items():
            for (b1, h1), c1 in local.items():
                b = b0 + b1
                h = h0 + h1
                if b <= board_cards and h <= hole_cards:
                    nxt[(b, h)] += c0 * c1
        total = dict(nxt)
    return total.get((board_cards, hole_cards), 0)


def exact_flop_hole_orbit_count() -> int:
    """Exact number of NLH flop+two-hole-card states modulo global suit relabeling.

    Burnside's lemma over the 24 suit permutations gives 1,286,792 orbits.
    This is the strategically lossless suit-isomorphic state count for one
    player's information at the flop before action history is added.
    """

    weighted = 0
    for cycle_lengths, multiplicity in S4_CYCLE_TYPES:
        weighted += multiplicity * fixed_partitioned_states(cycle_lengths)
    if weighted % 24 != 0:
        raise AssertionError("Burnside orbit count must be integral")
    return weighted // 24


def decision_scenario_count(num_players: int) -> int:
    """Number of nonterminal public FOLD/STAY decision histories for N players.

    For actors before BTN, every binary history is reachable. BTN does not act
    in the single history where every previous player folded, because the hand
    has already ended. Summing the decision histories yields 2**N - 2.
    """

    if not 2 <= num_players <= 8:
        raise ValueError("num_players must be between 2 and 8")
    return (1 << num_players) - 2


def exact_infoset_upper_count(num_players: int) -> int:
    """Dense upper count across all canonical flops and all public scenarios."""

    return exact_flop_hole_orbit_count() * decision_scenario_count(num_players)


def exact_state_space_summary() -> ExactStateSpaceSummary:
    canonical_flops = 1755
    naive = canonical_flops * 169
    exact = exact_flop_hole_orbit_count()
    return ExactStateSpaceSummary(
        canonical_flops=canonical_flops,
        naive_169_flop_states=naive,
        exact_flop_hole_orbits=exact,
        exact_vs_169_ratio=exact / naive,
    )
