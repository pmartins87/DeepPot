from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Sequence

from .cards import Card, full_deck, require_unique
from .evaluator import showdown_winners


@dataclass(frozen=True)
class HUEquity:
    wins: int
    ties: int
    losses: int

    @property
    def total(self) -> int:
        return self.wins + self.ties + self.losses

    @property
    def equity(self) -> float:
        if self.total == 0:
            raise ValueError("empty equity sample")
        return (self.wins + 0.5 * self.ties) / self.total


def exact_hu_equity_on_flop(
    hero: Sequence[Card],
    villain: Sequence[Card],
    flop: Sequence[Card],
) -> HUEquity:
    if len(hero) != 2 or len(villain) != 2 or len(flop) != 3:
        raise ValueError("expected 2 hero, 2 villain and 3 flop cards")
    known = tuple(hero) + tuple(villain) + tuple(flop)
    require_unique(known)
    known_set = set(known)
    remaining = [c for c in full_deck() if c not in known_set]
    wins = ties = losses = 0
    for turn, river in combinations(remaining, 2):
        winners = showdown_winners((hero, villain), tuple(flop) + (turn, river))
        if winners == (0,):
            wins += 1
        elif winners == (1,):
            losses += 1
        else:
            ties += 1
    return HUEquity(wins=wins, ties=ties, losses=losses)
