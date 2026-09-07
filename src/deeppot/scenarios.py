from __future__ import annotations

from typing import Sequence

from .game import Action


def actor_label(num_players: int, actor_index: int) -> str:
    if not 2 <= num_players <= 8:
        raise ValueError("num_players must be between 2 and 8")
    if not 0 <= actor_index < num_players:
        raise ValueError("actor_index out of range")
    return "BTN" if actor_index == num_players - 1 else f"A{actor_index}"


def history_code(actions: Sequence[Action]) -> str:
    return "".join("S" if a == Action.STAY else "F" for a in actions) or "ROOT"


def scenario_id(num_players: int, actor_index: int, prior_actions: Sequence[Action]) -> str:
    if actor_index != len(prior_actions):
        raise ValueError("actor_index must equal number of prior actions in fixed action order")
    return f"N{num_players}_{actor_label(num_players, actor_index)}_H{history_code(prior_actions)}"
