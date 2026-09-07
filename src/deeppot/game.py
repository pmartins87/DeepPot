from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Action(str, Enum):
    FOLD = "FOLD"
    STAY = "STAY"  # contributes exactly the initial pot (bet/call in UI terminology)


@dataclass(frozen=True)
class PotFoldRules:
    """Mechanical Pot Fold rules independent of card evaluation and rake.

    Player indices are already in flop action order, starting with the player in
    the SB *position* (Pot Fold does not charge an SB blind).
    """

    num_players: int
    ante: float

    def __post_init__(self) -> None:
        if self.num_players < 2:
            raise ValueError("num_players must be >= 2")
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
    """Single-flop-betting-round state.

    `active[i]` means player i has not folded.
    `acted[i]` means player i already made the one allowed flop decision.
    `stayed[i]` records whether player i contributed the fixed initial-pot amount.
    """

    rules: PotFoldRules
    active: tuple[bool, ...]
    acted: tuple[bool, ...]
    stayed: tuple[bool, ...]
    to_act: Optional[int]

    @classmethod
    def initial(cls, rules: PotFoldRules) -> "PotFoldState":
        n = rules.num_players
        return cls(
            rules=rules,
            active=(True,) * n,
            acted=(False,) * n,
            stayed=(False,) * n,
            to_act=0,
        )

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
        if action not in self.legal_actions():
            raise ValueError(f"illegal action: {action}")

        i = self.to_act
        active = list(self.active)
        acted = list(self.acted)
        stayed = list(self.stayed)

        acted[i] = True
        if action == Action.FOLD:
            active[i] = False
        else:
            stayed[i] = True

        # If only one player remains, the hand is over. This encodes the natural
        # last-player/no-op terminal used by the AoF tree as well. P0 keeps this
        # mechanic flagged for live-client confirmation before strategy publish.
        if sum(active) <= 1:
            nxt = None
        else:
            nxt = None
            for j in range(i + 1, self.rules.num_players):
                if active[j] and not acted[j]:
                    nxt = j
                    break
            if nxt is None:
                # Every still-active player has completed the one flop decision.
                # With >=2 active players, turn/river are chance-only showdown.
                nxt = None

        return PotFoldState(
            rules=self.rules,
            active=tuple(active),
            acted=tuple(acted),
            stayed=tuple(stayed),
            to_act=nxt,
        )
