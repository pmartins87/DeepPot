from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, Sequence

from .cards import Card, canonical_flop_hole_id, full_deck, require_unique
from .economics import PotFoldEconomy
from .evaluator import showdown_winners
from .game import Action, PotFoldRules, PotFoldState
from .scenarios import scenario_id

ACTIONS = (Action.FOLD, Action.STAY)


@dataclass
class InfoNode:
    regrets: list[float] = field(default_factory=lambda: [0.0, 0.0])
    strategy_sum: list[float] = field(default_factory=lambda: [0.0, 0.0])
    visits: int = 0

    def current_strategy(self) -> tuple[float, float]:
        positive = [max(0.0, r) for r in self.regrets]
        total = sum(positive)
        if total <= 0.0:
            return (0.5, 0.5)
        return (positive[0] / total, positive[1] / total)

    def average_strategy(self) -> tuple[float, float]:
        total = sum(self.strategy_sum)
        if total <= 0.0:
            return (0.5, 0.5)
        return (self.strategy_sum[0] / total, self.strategy_sum[1] / total)


@dataclass(frozen=True)
class SampledDeal:
    holes: tuple[tuple[Card, Card], ...]
    turn: Card
    river: Card


@dataclass
class SolveResult:
    iterations: int
    seed: int
    nodes: Dict[str, InfoNode]

    def average_policy(self) -> dict[str, tuple[float, float]]:
        return {key: node.average_strategy() for key, node in self.nodes.items()}


class ChanceSampledCFR:
    """Prototype base solver for a fixed-flop Pot Fold subgame.

    Chance is sampled once per iteration: private hands plus turn/river. The full
    binary action tree is then traversed. Information-set keys contain only what
    the acting player is allowed to know: player count, actor/history, flop and
    that player's hole cards.

    This mirrors DeepKK's CFR+/linear-average architecture while preserving an
    explicit caveat: rake makes total utility path-dependent, and N>2 is a
    multiplayer game. Output therefore remains experimental until it passes the
    dedicated stability and best-response gates in P4.
    """

    def __init__(
        self,
        *,
        num_players: int,
        flop: Sequence[Card],
        rake_pct: float = 0.0,
        rake_cap: float | None = None,
        seed: int = 1,
        cfr_plus: bool = True,
        linear_average: bool = True,
    ) -> None:
        if not 2 <= num_players <= 8:
            raise ValueError("num_players must be between 2 and 8")
        if len(flop) != 3:
            raise ValueError("flop must contain exactly 3 cards")
        require_unique(flop)
        self.num_players = num_players
        self.flop = tuple(flop)
        self.rules = PotFoldRules(num_players=num_players, ante=1.0)
        self.economy = PotFoldEconomy(
            num_players=num_players,
            ante=1.0,
            rake_pct=rake_pct,
            rake_cap=rake_cap,
        )
        self.rng = random.Random(seed)
        self.seed = seed
        self.cfr_plus = cfr_plus
        self.linear_average = linear_average
        self.nodes: Dict[str, InfoNode] = {}

    def _sample_deal(self) -> SampledDeal:
        excluded = set(self.flop)
        deck = [c for c in full_deck() if c not in excluded]
        self.rng.shuffle(deck)
        holes = []
        idx = 0
        for _ in range(self.num_players):
            holes.append((deck[idx], deck[idx + 1]))
            idx += 2
        turn, river = deck[idx], deck[idx + 1]
        return SampledDeal(tuple(holes), turn, river)

    def _terminal_utility(self, state: PotFoldState, deal: SampledDeal) -> tuple[float, ...]:
        active = [i for i, alive in enumerate(state.active) if alive]
        if not active:
            raise AssertionError("Pot Fold cannot end with zero active players")
        if len(active) == 1:
            winners = (active[0],)
        else:
            board = self.flop + (deal.turn, deal.river)
            active_hands = [deal.holes[i] for i in active]
            local_winners = showdown_winners(active_hands, board)
            winners = tuple(active[j] for j in local_winners)
        return self.economy.terminal_utilities(stayed=state.stayed, winners=winners)

    def _infoset_key(self, state: PotFoldState, deal: SampledDeal) -> str:
        assert state.to_act is not None
        actor = state.to_act
        prior_actions: list[Action] = []
        for i in range(actor):
            prior_actions.append(Action.STAY if state.stayed[i] else Action.FOLD)
        scen = scenario_id(self.num_players, actor, prior_actions)
        cards = canonical_flop_hole_id(self.flop, deal.holes[actor])
        return f"{scen}|{cards}"

    def _cfr(
        self,
        state: PotFoldState,
        deal: SampledDeal,
        reach: tuple[float, ...],
        iteration: int,
    ) -> tuple[float, ...]:
        if state.is_terminal:
            return self._terminal_utility(state, deal)

        actor = state.to_act
        assert actor is not None
        key = self._infoset_key(state, deal)
        node = self.nodes.setdefault(key, InfoNode())
        strategy = node.current_strategy()
        node.visits += 1

        action_utils: list[tuple[float, ...]] = []
        node_util = [0.0] * self.num_players
        for a_idx, action in enumerate(ACTIONS):
            next_reach = list(reach)
            next_reach[actor] *= strategy[a_idx]
            util = self._cfr(state.apply(action), deal, tuple(next_reach), iteration)
            action_utils.append(util)
            for p in range(self.num_players):
                node_util[p] += strategy[a_idx] * util[p]

        cf_reach = 1.0
        for p, prob in enumerate(reach):
            if p != actor:
                cf_reach *= prob
        for a_idx in range(2):
            delta = cf_reach * (action_utils[a_idx][actor] - node_util[actor])
            node.regrets[a_idx] += delta
            if self.cfr_plus:
                node.regrets[a_idx] = max(0.0, node.regrets[a_idx])

        weight = float(iteration) if self.linear_average else 1.0
        for a_idx in range(2):
            node.strategy_sum[a_idx] += weight * reach[actor] * strategy[a_idx]
        return tuple(node_util)

    def solve(self, iterations: int) -> SolveResult:
        if iterations <= 0:
            raise ValueError("iterations must be > 0")
        for iteration in range(1, iterations + 1):
            deal = self._sample_deal()
            self._cfr(
                PotFoldState.initial(self.rules),
                deal,
                (1.0,) * self.num_players,
                iteration,
            )
        return SolveResult(iterations=iterations, seed=self.seed, nodes=self.nodes)
