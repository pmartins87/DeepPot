from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Action(str, Enum):
    FOLD = "FOLD"
    STAY = "STAY"


@dataclass(frozen=True)
class PotFoldRules:
    """Mechanical Pot Fold rules independent of cards and rake.

    Player indices are in flop action order. Index N-1 is the BTN and acts last.
    Pot Fold charges antes, not SB/BB blinds; A0/A1/... are intentionally neutral
    labels until the live OpenHoldem seat mapping is frozen.
    """

    num_players: int
    ante: float

    def __post_init__(self) -> None:
        if not 2 <= self.num_players <= 8:
            raise ValueError("num_players must be between 2 and 8")
        if self.ante <= 0:
            raise ValueError("ante must be > 0")

    @property
    def initial_pot(self) -> float:
        return self.num_players * self.ante

    @property
    def stay_cost(self) -> float:
        return self.initial_pot


@dataclass(frozen=True)
class PotFoldState:
    rules: PotFoldRules
    active: tuple[bool, ...]
    acted: tuple[bool, ...]
    stayed: tuple[bool, ...]
    to_act: Optional[int]

    @classmethod
    def initial(cls, rules: PotFoldRules) -> "PotFoldState":
        n = rules.num_players
        return cls(rules, (True,) * n, (False,) * n, (False,) * n, 0)

    @property
    def active_count(self) -> int:
        return sum(self.active)

    @property
    def stay_count(self) -> int:
        return sum(self.stayed)

    @property
    def is_terminal(self) -> bool:
        return self.to_act is None

    @property
    def showdown(self) -> bool:
        return self.is_terminal and self.active_count >= 2

    @property
    def uncontested_winner(self) -> Optional[int]:
        if not self.is_terminal or self.active_count != 1:
            return None
        return next(i for i, alive in enumerate(self.active) if alive)

    @property
    def gross_pot(self) -> float:
        return self.rules.initial_pot + self.stay_count * self.rules.stay_cost

    def legal_actions(self) -> tuple[Action, ...]:
        if self.is_terminal:
            return ()
        return (Action.FOLD, Action.STAY)

    def apply(self, action: Action) -> "PotFoldState":
        if self.is_terminal or self.to_act is None:
            raise ValueError("cannot act in a terminal state")
        i = self.to_act
        active = list(self.active)
        acted = list(self.acted)
        stayed = list(self.stayed)
        acted[i] = True
        if action == Action.FOLD:
            active[i] = False
        elif action == Action.STAY:
            stayed[i] = True
        else:
            raise ValueError(f"illegal action: {action}")

        # Live semantics confirmed by user observation: if every player before
        # the final survivor folds, the survivor wins immediately and does not
        # make/pay the fixed STAY action. Rake is handled by the economy layer.
        if sum(active) <= 1:
            nxt = None
        else:
            nxt = next(
                (j for j in range(i + 1, self.rules.num_players) if active[j] and not acted[j]),
                None,
            )
        return PotFoldState(self.rules, tuple(active), tuple(acted), tuple(stayed), nxt)
