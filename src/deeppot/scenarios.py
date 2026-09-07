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


def scenario_dense_id(num_players: int, actor_index: int, prior_actions: Sequence[Action]) -> int:
    """Dense 0-based public-history ID for a fixed player-count mode.

    FOLD is bit 0 and STAY is bit 1 in action order. Actors before BTN receive
    all 2**actor histories. BTN's all-FOLD history is omitted because the hand
    has already terminated and BTN never acts there.

    The resulting IDs are contiguous from 0 through (2**N - 3), i.e. exactly
    2**N - 2 nonterminal decision scenarios.
    """

    if not 2 <= num_players <= 8:
        raise ValueError("num_players must be between 2 and 8")
    if not 0 <= actor_index < num_players:
        raise ValueError("actor_index out of range")
    if actor_index != len(prior_actions):
        raise ValueError("actor_index must equal number of prior actions in fixed action order")

    bits = 0
    for i, action in enumerate(prior_actions):
        if action == Action.STAY:
            bits |= 1 << i
        elif action != Action.FOLD:
            raise ValueError(f"unsupported action in history: {action}")

    offset = (1 << actor_index) - 1
    if actor_index == num_players - 1:
        if bits == 0:
            raise ValueError("BTN all-FOLD history is terminal and has no decision scenario")
        return offset + bits - 1
    return offset + bits
