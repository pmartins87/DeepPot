from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .cards import Card
from .evaluator import evaluate_seven
from .solver import ChanceSampledCFR, InfoNode, SolveResult


@dataclass(frozen=True)
class FastSampledDeal:
    holes: tuple[tuple[Card, Card], ...]
    hole_state_ids: tuple[int, ...]
    rank_keys: tuple[tuple[int, ...], ...]


@dataclass(frozen=True)
class TerminalSpec:
    active: tuple[int, ...]
    stayed_mask: int
    base_utility: tuple[float, ...]
    net_pot: float
    singleton_utility: tuple[float, ...] | None


class FastChanceSampledCFR(ChanceSampledCFR):
    """Mathematically equivalent exact CFR kernel with a precomputed public tree.

    This is a performance candidate only. It deliberately preserves the same:

    * exact private-state index;
    * chance shuffle/RNG trajectory;
    * CFR+ regret update;
    * linear-average weighting;
    * FOLD-then-STAY traversal order;
    * terminal economy and tie splitting.

    The speedups come from removing repeated Python work from the hot path:

    * no immutable ``PotFoldState`` allocation on every branch;
    * no repeated ``scenario_dense_id`` reconstruction;
    * hole-state IDs are computed once per dealt player, not once per public node;
    * terminal contribution/rake constants are precomputed per public leaf;
    * rank objects are converted once per player/deal to plain tuple keys;
    * reach probabilities are updated/restored in place instead of copied twice
      at every public decision node;
    * ``dict.get`` avoids constructing throw-away ``InfoNode`` objects on hits.

    It is not eligible for production until differential tests and a target-Ryzen
    benchmark demonstrate equivalence and a material wall-clock gain.
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._build_public_tree()

    @staticmethod
    def _sid(num_players: int, actor: int, prior_stay_mask: int) -> int:
        offset = (1 << actor) - 1
        if actor == num_players - 1:
            if prior_stay_mask == 0:
                raise ValueError("BTN all-FOLD history is terminal")
            return offset + prior_stay_mask - 1
        return offset + prior_stay_mask

    def _make_terminal_spec(self, active_mask: int, stayed_mask: int) -> TerminalSpec:
        active = tuple(i for i in range(self.num_players) if active_mask & (1 << i))
        if not active:
            raise AssertionError("Pot Fold cannot terminate with zero active players")
        stayed = tuple(bool(stayed_mask & (1 << i)) for i in range(self.num_players))
        base = tuple(-self.economy.contribution(flag) for flag in stayed)
        net = self.economy.net_terminal_pot(sum(stayed))
        singleton = None
        if len(active) == 1:
            out = list(base)
            out[active[0]] += net
            singleton = tuple(out)
        return TerminalSpec(
            active=active,
            stayed_mask=stayed_mask,
            base_utility=base,
            net_pot=net,
            singleton_utility=singleton,
        )

    def _build_public_tree(self) -> None:
        scenario_count = (1 << self.num_players) - 2
        actor_by_sid = [-1] * scenario_count
        fold_child = [0] * scenario_count
        stay_child = [0] * scenario_count
        terminal_specs: list[TerminalSpec] = []
        terminal_by_key: dict[tuple[int, int], int] = {}

        def terminal_desc(active_mask: int, stayed_mask: int) -> int:
            key = (active_mask, stayed_mask)
            idx = terminal_by_key.get(key)
            if idx is None:
                idx = len(terminal_specs)
                terminal_by_key[key] = idx
                terminal_specs.append(self._make_terminal_spec(active_mask, stayed_mask))
            return -idx - 1

        all_mask = (1 << self.num_players) - 1
        for actor in range(self.num_players):
            for bits in range(1 << actor):
                if actor == self.num_players - 1 and bits == 0:
                    continue
                sid = self._sid(self.num_players, actor, bits)
                actor_by_sid[sid] = actor

                # Prior STAY players remain active. Prior FOLD players are gone.
                future_mask = all_mask & ~((1 << actor) - 1)
                active_mask = bits | future_mask

                # FOLD branch.
                fold_active = active_mask & ~(1 << actor)
                if fold_active.bit_count() <= 1:
                    fold_child[sid] = terminal_desc(fold_active, bits)
                else:
                    fold_child[sid] = self._sid(self.num_players, actor + 1, bits)

                # STAY branch.
                stay_bits = bits | (1 << actor)
                if actor == self.num_players - 1:
                    stay_child[sid] = terminal_desc(active_mask, stay_bits)
                else:
                    stay_child[sid] = self._sid(self.num_players, actor + 1, stay_bits)

        if any(actor < 0 for actor in actor_by_sid):
            raise AssertionError("precomputed public tree did not fill every decision scenario")
        self._fast_actor_by_sid = tuple(actor_by_sid)
        self._fast_fold_child = tuple(fold_child)
        self._fast_stay_child = tuple(stay_child)
        self._fast_terminal_specs = tuple(terminal_specs)

    def _sample_fast_deal(self) -> FastSampledDeal:
        # Keep the exact same shuffle call and card consumption order as the
        # reference solver so seed-identical differential tests share chance.
        deck = list(self._deal_deck)
        self.rng.shuffle(deck)
        holes: list[tuple[Card, Card]] = []
        hole_ids: list[int] = []
        idx = 0
        for _ in range(self.num_players):
            hole = (deck[idx], deck[idx + 1])
            holes.append(hole)
            raw_hole = hole if hole[0] < hole[1] else (hole[1], hole[0])
            hole_ids.append(self._raw_hole_to_state_id[raw_hole])
            idx += 2
        turn, river = deck[idx], deck[idx + 1]
        board = self.flop + (turn, river)
        rank_keys = tuple(evaluate_seven(hole + board).as_tuple() for hole in holes)
        return FastSampledDeal(tuple(holes), tuple(hole_ids), rank_keys)

    def _terminal_fast(self, desc: int, deal: FastSampledDeal) -> tuple[float, ...]:
        spec = self._fast_terminal_specs[-desc - 1]
        if spec.singleton_utility is not None:
            return spec.singleton_utility

        active = spec.active
        rank_keys = deal.rank_keys
        best = rank_keys[active[0]]
        for player in active[1:]:
            rank = rank_keys[player]
            if rank > best:
                best = rank

        winners: list[int] = []
        for player in active:
            if rank_keys[player] == best:
                winners.append(player)
        payout_each = spec.net_pot / len(winners)
        out = list(spec.base_utility)
        for player in winners:
            out[player] += payout_each
        return tuple(out)

    def _cfr_fast(
        self,
        sid: int,
        deal: FastSampledDeal,
        reach: list[float],
        iteration_weight: float,
    ) -> tuple[float, ...]:
        actor = self._fast_actor_by_sid[sid]
        key = sid * self.hole_state_count + deal.hole_state_ids[actor]
        node = self.nodes.get(key)
        if node is None:
            node = InfoNode()
            self.nodes[key] = node

        r0 = node.regrets[0]
        r1 = node.regrets[1]
        p0 = r0 if r0 > 0.0 else 0.0
        p1 = r1 if r1 > 0.0 else 0.0
        total = p0 + p1
        if total <= 0.0:
            s0 = 0.5
            s1 = 0.5
        else:
            s0 = p0 / total
            s1 = p1 / total
        node.visits += 1

        old_actor_reach = reach[actor]

        # Reference traversal order is FOLD first, STAY second.
        reach[actor] = old_actor_reach * s0
        child0 = self._fast_fold_child[sid]
        if child0 >= 0:
            util0 = self._cfr_fast(child0, deal, reach, iteration_weight)
        else:
            util0 = self._terminal_fast(child0, deal)

        reach[actor] = old_actor_reach * s1
        child1 = self._fast_stay_child[sid]
        if child1 >= 0:
            util1 = self._cfr_fast(child1, deal, reach, iteration_weight)
        else:
            util1 = self._terminal_fast(child1, deal)

        reach[actor] = old_actor_reach

        node_util = tuple(s0 * util0[p] + s1 * util1[p] for p in range(self.num_players))
        actor_util = node_util[actor]

        cf_reach = 1.0
        for p in range(self.num_players):
            if p != actor:
                cf_reach *= reach[p]

        nr0 = node.regrets[0] + cf_reach * (util0[actor] - actor_util)
        nr1 = node.regrets[1] + cf_reach * (util1[actor] - actor_util)
        if self.cfr_plus:
            if nr0 < 0.0:
                nr0 = 0.0
            if nr1 < 0.0:
                nr1 = 0.0
        node.regrets[0] = nr0
        node.regrets[1] = nr1

        avg_scale = iteration_weight * old_actor_reach
        node.strategy_sum[0] += avg_scale * s0
        node.strategy_sum[1] += avg_scale * s1
        return node_util

    def _run_iterations(self, iterations: int, *, iteration_offset: int) -> SolveResult:
        if iterations <= 0:
            raise ValueError("iterations must be > 0")
        if iteration_offset < 0:
            raise ValueError("iteration_offset must be >= 0")
        root_sid = 0
        reach = [1.0] * self.num_players
        for local_iteration in range(1, iterations + 1):
            iteration = iteration_offset + local_iteration
            deal = self._sample_fast_deal()
            self._cfr_fast(root_sid, deal, reach, float(iteration))
        return SolveResult(
            iterations=iteration_offset + iterations,
            seed=self.seed,
            nodes=self.nodes,
            hole_state_count=self.hole_state_count,
            flop_key=self.exact_index.flop_key,
        )
