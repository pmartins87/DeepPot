from __future__ import annotations

import random
from dataclasses import dataclass, field
from itertools import combinations
from typing import Dict, Sequence

from .cards import Card, full_deck, require_unique
from .economics import PotFoldEconomy
from .evaluator import HandRank, evaluate_seven
from .exact_index import ExactFlopHoleIndex
from .game import Action, PotFoldRules, PotFoldState
from .scenarios import scenario_dense_id

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
    final_ranks: tuple[HandRank, ...]


@dataclass
class SolveResult:
    iterations: int
    seed: int
    nodes: Dict[int, InfoNode]
    hole_state_count: int
    flop_key: tuple[tuple[int, int], ...]

    def average_policy(self) -> dict[int, tuple[float, float]]:
        return {key: node.average_strategy() for key, node in self.nodes.items()}

    def decode_infoset_key(self, key: int) -> tuple[int, int]:
        """Return `(public_scenario_id, exact_hole_state_id)` for a dense key."""

        if key < 0:
            raise ValueError("infoset key must be non-negative")
        return divmod(key, self.hole_state_count)


class ChanceSampledCFR:
    """Exact-state base-solver candidate for one fixed Pot Fold flop.

    Chance is sampled once per iteration: private hands plus turn/river. The full
    binary action tree is then traversed. Information sets preserve the exact
    flop-relative two-card state modulo only true global suit isomorphism.

    Hot-path keys are dense integers:

        public_scenario_id * exact_hole_state_count + exact_hole_state_id

    The 1,176 possible raw hole combinations on the fixed flop are mapped to
    exact canonical state IDs once at initialization, avoiding repeated 24-suit
    canonicalization inside every CFR node visit.

    Terminal showdown ranks are also computed exactly ONCE per player per sampled
    deal. Every terminal public history for that deal reuses those ranks. This is
    especially important for N=5..8, where a full binary public tree would
    otherwise re-evaluate the same seven-card hands many times. The optimization
    changes no game state, chance distribution, payoff, or strategic abstraction.

    Persistent DeepPot training resumes by restoring this object's nodes, RNG
    state and the global linear-averaging iteration offset. Continuing from an
    offset therefore executes the exact same recurrence as one uninterrupted run.
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
        self.nodes: Dict[int, InfoNode] = {}

        # Exact per-flop state index. This is canonicalization only; no strategic
        # card abstraction or bucketing is performed.
        self.exact_index = ExactFlopHoleIndex.build(self.flop)
        self.hole_state_count = len(self.exact_index)

        excluded = set(self.flop)
        self._deal_deck = tuple(c for c in full_deck() if c not in excluded)

        # Precompute all 1,176 legal raw hole-pair -> exact dense-state mappings
        # for this fixed flop. CFR then needs only a two-card tuple dictionary
        # lookup instead of 24 suit permutations at each node.
        raw_hole_to_state_id: dict[tuple[Card, Card], int] = {}
        for hole in combinations(self._deal_deck, 2):
            key = tuple(sorted(hole))
            raw_hole_to_state_id[key] = self.exact_index.state_id(self.flop, hole)
        self._raw_hole_to_state_id = raw_hole_to_state_id

    def _sample_deal(self) -> SampledDeal:
        deck = list(self._deal_deck)
        self.rng.shuffle(deck)
        holes = []
        idx = 0
        for _ in range(self.num_players):
            holes.append((deck[idx], deck[idx + 1]))
            idx += 2
        turn, river = deck[idx], deck[idx + 1]
        board = self.flop + (turn, river)
        final_ranks = tuple(evaluate_seven(tuple(hole) + board) for hole in holes)
        return SampledDeal(tuple(holes), turn, river, final_ranks)

    def _terminal_utility(self, state: PotFoldState, deal: SampledDeal) -> tuple[float, ...]:
        active = [i for i, alive in enumerate(state.active) if alive]
        if not active:
            raise AssertionError("Pot Fold cannot end with zero active players")
        if len(active) == 1:
            winners = (active[0],)
        else:
            best = max(deal.final_ranks[i] for i in active)
            winners = tuple(i for i in active if deal.final_ranks[i] == best)
        return self.economy.terminal_utilities(stayed=state.stayed, winners=winners)

    def _infoset_key(self, state: PotFoldState, deal: SampledDeal) -> int:
        assert state.to_act is not None
        actor = state.to_act
        prior_actions: list[Action] = []
        for i in range(actor):
            prior_actions.append(Action.STAY if state.stayed[i] else Action.FOLD)
        public_id = scenario_dense_id(self.num_players, actor, prior_actions)
        raw_hole = tuple(sorted(deal.holes[actor]))
        hole_id = self._raw_hole_to_state_id[raw_hole]
        return public_id * self.hole_state_count + hole_id

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

    def _run_iterations(self, iterations: int, *, iteration_offset: int) -> SolveResult:
        if iterations <= 0:
            raise ValueError("iterations must be > 0")
        if iteration_offset < 0:
            raise ValueError("iteration_offset must be >= 0")
        for local_iteration in range(1, iterations + 1):
            iteration = iteration_offset + local_iteration
            deal = self._sample_deal()
            self._cfr(
                PotFoldState.initial(self.rules),
                deal,
                (1.0,) * self.num_players,
                iteration,
            )
        return SolveResult(
            iterations=iteration_offset + iterations,
            seed=self.seed,
            nodes=self.nodes,
            hole_state_count=self.hole_state_count,
            flop_key=self.exact_index.flop_key,
        )

    def solve(self, iterations: int) -> SolveResult:
        """Start a fresh trajectory at global linear-average iteration 1."""
        return self._run_iterations(iterations, iteration_offset=0)

    def continue_solve(self, additional_iterations: int, *, completed_iterations: int) -> SolveResult:
        """Continue a restored trajectory without resetting linear-average weights."""
        return self._run_iterations(additional_iterations, iteration_offset=completed_iterations)
