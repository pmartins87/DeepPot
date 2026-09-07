from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Sequence

from .cards import Card, require_unique


@dataclass(frozen=True)
class HandRank:
    category: int
    kickers: tuple[int, ...]

    def as_tuple(self) -> tuple[int, ...]:
        return (self.category, *self.kickers)

    def __lt__(self, other: "HandRank") -> bool:
        return self.as_tuple() < other.as_tuple()


def _straight_high(ranks: Sequence[int]) -> int | None:
    uniq = sorted(set(ranks), reverse=True)
    if 14 in uniq:
        uniq.append(1)
    for i in range(len(uniq) - 4):
        window = uniq[i : i + 5]
        if window[0] - window[4] == 4 and len(set(window)) == 5:
            return window[0]
    return None


def _straight_high_mask(mask: int) -> int | None:
    """Fast straight-high lookup from a 13-bit rank mask (deuce bit 0, ace bit 12)."""

    # Standard broadway through six-high straights.
    for high in range(14, 5 - 1, -1):
        low = high - 4
        needed = 0
        for rank in range(low, high + 1):
            needed |= 1 << (rank - 2)
        if mask & needed == needed:
            return high
    # Wheel A-2-3-4-5.
    wheel = (1 << (14 - 2)) | (1 << 0) | (1 << 1) | (1 << 2) | (1 << 3)
    if mask & wheel == wheel:
        return 5
    return None


def evaluate_five(cards: Sequence[Card]) -> HandRank:
    if len(cards) != 5:
        raise ValueError("evaluate_five requires exactly 5 cards")
    require_unique(cards)
    ranks = [c.rank for c in cards]
    suits = [c.suit for c in cards]
    flush = len(set(suits)) == 1
    straight_high = _straight_high(ranks)

    counts: dict[int, int] = {}
    for r in ranks:
        counts[r] = counts.get(r, 0) + 1
    groups = sorted(((count, rank) for rank, count in counts.items()), reverse=True)

    if flush and straight_high is not None:
        return HandRank(8, (straight_high,))
    if groups[0][0] == 4:
        quad = groups[0][1]
        kicker = max(r for r in ranks if r != quad)
        return HandRank(7, (quad, kicker))
    if sorted(counts.values()) == [2, 3]:
        trip = max(r for r, c in counts.items() if c == 3)
        pair = max(r for r, c in counts.items() if c == 2)
        return HandRank(6, (trip, pair))
    if flush:
        return HandRank(5, tuple(sorted(ranks, reverse=True)))
    if straight_high is not None:
        return HandRank(4, (straight_high,))
    if groups[0][0] == 3:
        trip = groups[0][1]
        kickers = tuple(sorted((r for r in ranks if r != trip), reverse=True))
        return HandRank(3, (trip, *kickers))
    pairs = sorted((r for r, c in counts.items() if c == 2), reverse=True)
    if len(pairs) == 2:
        kicker = max(r for r in ranks if r not in pairs)
        return HandRank(2, (pairs[0], pairs[1], kicker))
    if len(pairs) == 1:
        pair = pairs[0]
        kickers = tuple(sorted((r for r in ranks if r != pair), reverse=True))
        return HandRank(1, (pair, *kickers))
    return HandRank(0, tuple(sorted(ranks, reverse=True)))


def evaluate_seven_reference(cards: Sequence[Card]) -> HandRank:
    """Slow combination-based reference evaluator retained for differential tests."""

    if len(cards) != 7:
        raise ValueError("evaluate_seven_reference requires exactly 7 cards")
    require_unique(cards)
    return max(evaluate_five(c) for c in combinations(cards, 5))


def evaluate_seven(cards: Sequence[Card]) -> HandRank:
    """Direct exact 7-card evaluator without enumerating 21 five-card subsets.

    The ranking is identical to `evaluate_seven_reference`; this implementation
    derives the best category directly from rank/suit counts and masks. It is a
    performance optimization only and performs no card abstraction.
    """

    if len(cards) != 7:
        raise ValueError("evaluate_seven requires exactly 7 cards")
    require_unique(cards)

    rank_counts = [0] * 15
    suit_ranks: list[list[int]] = [[], [], [], []]
    rank_mask = 0
    for c in cards:
        rank_counts[c.rank] += 1
        suit_ranks[c.suit].append(c.rank)
        rank_mask |= 1 << (c.rank - 2)

    # Straight flush: any suit with >=5 cards can contain one.
    for ranks in suit_ranks:
        if len(ranks) >= 5:
            mask = 0
            for r in ranks:
                mask |= 1 << (r - 2)
            high = _straight_high_mask(mask)
            if high is not None:
                return HandRank(8, (high,))

    quads = [r for r in range(14, 1, -1) if rank_counts[r] == 4]
    if quads:
        quad = quads[0]
        kicker = max(r for r in range(2, 15) if r != quad and rank_counts[r] > 0)
        return HandRank(7, (quad, kicker))

    trips = [r for r in range(14, 1, -1) if rank_counts[r] >= 3]
    pairish = [r for r in range(14, 1, -1) if rank_counts[r] >= 2]
    if trips:
        trip = trips[0]
        pair_candidates = [r for r in pairish if r != trip]
        if pair_candidates:
            return HandRank(6, (trip, pair_candidates[0]))

    # Flush: with seven total cards at most one suit can have five or more.
    for ranks in suit_ranks:
        if len(ranks) >= 5:
            return HandRank(5, tuple(sorted(ranks, reverse=True)[:5]))

    straight_high = _straight_high_mask(rank_mask)
    if straight_high is not None:
        return HandRank(4, (straight_high,))

    if trips:
        trip = trips[0]
        kickers = [r for r in range(14, 1, -1) if r != trip and rank_counts[r] > 0][:2]
        return HandRank(3, (trip, *kickers))

    pairs = [r for r in range(14, 1, -1) if rank_counts[r] >= 2]
    if len(pairs) >= 2:
        hi, lo = pairs[:2]
        kicker = max(r for r in range(2, 15) if r not in (hi, lo) and rank_counts[r] > 0)
        return HandRank(2, (hi, lo, kicker))

    if len(pairs) == 1:
        pair = pairs[0]
        kickers = [r for r in range(14, 1, -1) if r != pair and rank_counts[r] > 0][:3]
        return HandRank(1, (pair, *kickers))

    highs = [r for r in range(14, 1, -1) if rank_counts[r] > 0][:5]
    return HandRank(0, tuple(highs))


def showdown_winners(hands: Sequence[Sequence[Card]], board: Sequence[Card]) -> tuple[int, ...]:
    if len(board) != 5:
        raise ValueError("board must contain exactly 5 cards")
    if not hands:
        raise ValueError("at least one hand is required")
    all_cards = tuple(board) + tuple(c for hand in hands for c in hand)
    require_unique(all_cards)
    ranks = [evaluate_seven(tuple(hand) + tuple(board)) for hand in hands]
    best = max(ranks)
    return tuple(i for i, rank in enumerate(ranks) if rank == best)
