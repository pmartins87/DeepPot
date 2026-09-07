from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Sequence

from .cards import (
    Card,
    SUIT_PERMUTATIONS,
    canonical_flop_hole_key,
    canonical_flop_key,
    full_deck,
    require_unique,
)

CardTuple = tuple[int, int]
FlopKey = tuple[CardTuple, ...]
HoleKey = tuple[CardTuple, ...]


def _mapped_sorted(cards: Sequence[Card], suit_perm: tuple[int, ...]) -> tuple[CardTuple, ...]:
    return tuple(sorted((c.rank, suit_perm[c.suit]) for c in cards))


def _cards_from_key(key: Sequence[CardTuple]) -> tuple[Card, ...]:
    return tuple(Card(rank, suit) for rank, suit in key)


def flop_stabilizer(canonical_flop: Sequence[Card]) -> tuple[tuple[int, ...], ...]:
    """Suit permutations that leave a canonical flop set unchanged.

    These are exact game symmetries. Quotienting hole cards by this stabilizer
    loses no strategic information.
    """

    key = tuple(sorted((c.rank, c.suit) for c in canonical_flop))
    return tuple(p for p in SUIT_PERMUTATIONS if _mapped_sorted(canonical_flop, p) == key)


@dataclass(frozen=True)
class ExactFlopHoleIndex:
    """Dense integer IDs for every exact hole state on one canonical flop.

    `hole_keys` contains only exact suit-isomorphic orbits under the flop's suit
    stabilizer. No equity, rank-class, draw-class, or potential abstraction is
    performed.
    """

    flop_key: FlopKey
    hole_keys: tuple[HoleKey, ...]
    stabilizer_size: int
    _hole_to_id: dict[HoleKey, int]

    @classmethod
    def build(cls, flop: Sequence[Card]) -> "ExactFlopHoleIndex":
        if len(flop) != 3:
            raise ValueError("flop must contain exactly 3 cards")
        require_unique(flop)

        flop_key = canonical_flop_key(flop)
        canonical_flop = _cards_from_key(flop_key)
        stabilizer = flop_stabilizer(canonical_flop)
        excluded = set(canonical_flop)
        remaining = tuple(c for c in full_deck() if c not in excluded)

        keys: set[HoleKey] = set()
        for hole in combinations(remaining, 2):
            keys.add(min(_mapped_sorted(hole, p) for p in stabilizer))

        hole_keys = tuple(sorted(keys))
        hole_to_id = {key: i for i, key in enumerate(hole_keys)}
        return cls(
            flop_key=flop_key,
            hole_keys=hole_keys,
            stabilizer_size=len(stabilizer),
            _hole_to_id=hole_to_id,
        )

    def __len__(self) -> int:
        return len(self.hole_keys)

    def state_id(self, flop: Sequence[Card], hole: Sequence[Card]) -> int:
        """Map an arbitrary suit-labeled flop+hole state to this exact dense ID."""

        fkey, hkey = canonical_flop_hole_key(flop, hole)
        if fkey != self.flop_key:
            raise ValueError("state belongs to a different canonical flop")
        try:
            return self._hole_to_id[hkey]
        except KeyError as exc:
            raise AssertionError("canonical hole state missing from exact index") from exc

    def hole_key(self, state_id: int) -> HoleKey:
        return self.hole_keys[state_id]
