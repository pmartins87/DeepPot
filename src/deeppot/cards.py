from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations, permutations
from typing import Iterable, Sequence

RANK_CHARS = "23456789TJQKA"
SUIT_CHARS = "cdhs"
RANK_TO_VALUE = {r: i + 2 for i, r in enumerate(RANK_CHARS)}
VALUE_TO_RANK = {v: r for r, v in RANK_TO_VALUE.items()}
SUIT_TO_VALUE = {s: i for i, s in enumerate(SUIT_CHARS)}
VALUE_TO_SUIT = {v: s for s, v in SUIT_TO_VALUE.items()}
SUIT_PERMUTATIONS = tuple(permutations(range(4)))


@dataclass(frozen=True, order=True)
class Card:
    rank: int
    suit: int

    def __post_init__(self) -> None:
        if self.rank < 2 or self.rank > 14:
            raise ValueError(f"invalid rank: {self.rank}")
        if self.suit < 0 or self.suit > 3:
            raise ValueError(f"invalid suit: {self.suit}")

    @classmethod
    def parse(cls, text: str) -> "Card":
        text = text.strip()
        if len(text) != 2 or text[0].upper() not in RANK_TO_VALUE or text[1].lower() not in SUIT_TO_VALUE:
            raise ValueError(f"invalid card: {text!r}")
        return cls(RANK_TO_VALUE[text[0].upper()], SUIT_TO_VALUE[text[1].lower()])

    def __str__(self) -> str:
        return VALUE_TO_RANK[self.rank] + VALUE_TO_SUIT[self.suit]


def parse_cards(texts: Iterable[str]) -> tuple[Card, ...]:
    cards = tuple(Card.parse(t) for t in texts)
    require_unique(cards)
    return cards


def full_deck() -> tuple[Card, ...]:
    return tuple(Card(rank, suit) for rank in range(2, 15) for suit in range(4))


def require_unique(cards: Sequence[Card]) -> None:
    if len(set(cards)) != len(cards):
        raise ValueError("duplicate cards")


def _mapped_sorted(cards: Sequence[Card], suit_perm: tuple[int, ...]) -> tuple[tuple[int, int], ...]:
    return tuple(sorted((c.rank, suit_perm[c.suit]) for c in cards))


def canonical_flop_key(flop: Sequence[Card]) -> tuple[tuple[int, int], ...]:
    if len(flop) != 3:
        raise ValueError("flop must contain exactly 3 cards")
    require_unique(flop)
    return min(_mapped_sorted(flop, p) for p in SUIT_PERMUTATIONS)


def canonical_flop_hole_key(
    flop: Sequence[Card],
    hole: Sequence[Card],
) -> tuple[tuple[tuple[int, int], ...], tuple[tuple[int, int], ...]]:
    if len(flop) != 3:
        raise ValueError("flop must contain exactly 3 cards")
    if len(hole) != 2:
        raise ValueError("hole must contain exactly 2 cards")
    require_unique(tuple(flop) + tuple(hole))
    return min(
        (_mapped_sorted(flop, p), _mapped_sorted(hole, p))
        for p in SUIT_PERMUTATIONS
    )


def encode_card_tuples(cards: Sequence[tuple[int, int]]) -> str:
    return "".join(VALUE_TO_RANK[r] + VALUE_TO_SUIT[s] for r, s in cards)


def canonical_flop_id(flop: Sequence[Card]) -> str:
    return encode_card_tuples(canonical_flop_key(flop))


def canonical_flop_hole_id(flop: Sequence[Card], hole: Sequence[Card]) -> str:
    f, h = canonical_flop_hole_key(flop, hole)
    return f"{encode_card_tuples(f)}|{encode_card_tuples(h)}"


def enumerate_canonical_flops() -> tuple[tuple[tuple[int, int], ...], ...]:
    keys = {canonical_flop_key(flop) for flop in combinations(full_deck(), 3)}
    return tuple(sorted(keys))
