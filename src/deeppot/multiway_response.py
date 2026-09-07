from __future__ import annotations

import argparse
import csv
import json
import math
import random
from dataclasses import asdict, dataclass
from itertools import combinations
from pathlib import Path
from typing import Mapping, Sequence

from .cards import Card, full_deck, require_unique
from .evaluator import evaluate_seven
from .exact_index import ExactFlopHoleIndex
from .state_space import decision_scenario_count

MULTIWAY_RESPONSE_VERSION = "2026-09-07.1"


@dataclass
class RunningStats:
    n: int = 0
    mean: float = 0.0
    m2: float = 0.0

    def add(self, value: float) -> None:
        self.n += 1
        delta = value - self.mean
        self.mean += delta / self.n
        self.m2 += delta * (value - self.mean)

    @property
    def variance(self) -> float:
        return self.m2 / (self.n - 1) if self.n > 1 else 0.0

    @property
    def std_error(self) -> float:
        return math.sqrt(self.variance / self.n) if self.n > 0 else 0.0

    def estimate(self) -> "MetricEstimate":
        half = 1.959963984540054 * self.std_error
        return MetricEstimate(
            mean=self.mean,
            std_error=self.std_error,
            ci95_low=self.mean - half,
            ci95_high=self.mean + half,
            samples=self.n,
        )


@dataclass(frozen=True)
class MetricEstimate:
    mean: float
    std_error: float
    ci95_low: float
    ci95_high: float
    samples: int


@dataclass(frozen=True)
class PublicTreeNode:
    actor: int | None
    public_id: int | None
    folded_mask: int
    stayed_mask: int
    depth: int
    fold_child: int | None = None
    stay_child: int | None = None

    @property
    def terminal(self) -> bool:
        return self.actor is None


@dataclass(frozen=True)
class MultiwayResponseReport:
    num_players: int
    flop: tuple[str, str, str]
    exact_hole_states: int
    public_scenarios: int
    learn_samples: int
    eval_samples: int
    seed: int
    rake_pct: float
    rake_cap: float | None
    profile_ev: tuple[MetricEstimate, ...]
    unilateral_gain: tuple[MetricEstimate, ...]
    total_unilateral_gain: MetricEstimate
    br_stay_states: tuple[int, ...]
    unreachable_infosets: tuple[int, ...]
    strategic_card_abstraction: str = "none"
    exact_symmetry_reduction: str = "global_suit_isomorphism_only"
    response_method: str = "split_sample_exact_public_tree_unilateral_best_response"


def parse_flop(text: str) -> tuple[Card, Card, Card]:
    tokens = text.replace(",", " ").split()
    if len(tokens) != 3:
        raise ValueError("flop must contain exactly three cards")
    flop = tuple(Card.parse(token) for token in tokens)
    require_unique(flop)
    return flop  # type: ignore[return-value]


def load_policy_csv(path: str | Path) -> dict[int, tuple[float, float]]:
    out: dict[int, tuple[float, float]] = {}
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"infoset_key", "p_fold", "p_stay"}
        if not required.issubset(set(reader.fieldnames or ())):
            raise ValueError(f"policy CSV must contain columns {sorted(required)}")
        for row in reader:
            key = int(row["infoset_key"])
            p_fold = float(row["p_fold"])
            p_stay = float(row["p_stay"])
            if key in out:
                raise ValueError(f"duplicate infoset key {key}")
            if p_fold < 0.0 or p_stay < 0.0 or abs((p_fold + p_stay) - 1.0) > 1e-6:
                raise ValueError(f"invalid policy probabilities at infoset {key}")
            out[key] = (p_fold, p_stay)
    return out


def _public_id(num_players: int, actor: int, stayed_mask: int) -> int:
    """Fast equivalent of scenario_dense_id for the fixed binary action order."""

    prior_bits = stayed_mask & ((1 << actor) - 1)
    offset = (1 << actor) - 1
    if actor == num_players - 1:
        if prior_bits == 0:
            raise AssertionError("BTN all-fold history is terminal")
        return offset + prior_bits - 1
    return offset + prior_bits


def _build_public_tree(num_players: int) -> tuple[tuple[PublicTreeNode, ...], int, tuple[int, ...]]:
    if not 2 <= num_players <= 8:
        raise ValueError("num_players must be between 2 and 8")

    nodes: list[PublicTreeNode] = []
    all_mask = (1 << num_players) - 1

    def build(actor: int, folded_mask: int, stayed_mask: int) -> int:
        active_count = (all_mask ^ folded_mask).bit_count()
        if actor >= num_players or active_count <= 1:
            idx = len(nodes)
            nodes.append(
                PublicTreeNode(
                    actor=None,
                    public_id=None,
                    folded_mask=folded_mask,
                    stayed_mask=stayed_mask,
                    depth=actor,
                )
            )
            return idx

        fold_child = build(actor + 1, folded_mask | (1 << actor), stayed_mask)
        stay_child = build(actor + 1, folded_mask, stayed_mask | (1 << actor))
        public_id = _public_id(num_players, actor, stayed_mask)
        idx = len(nodes)
        nodes.append(
            PublicTreeNode(
                actor=actor,
                public_id=public_id,
                folded_mask=folded_mask,
                stayed_mask=stayed_mask,
                depth=actor,
                fold_child=fold_child,
                stay_child=stay_child,
            )
        )
        return idx

    root = build(0, 0, 0)
    scenario_count = decision_scenario_count(num_players)
    actor_by_public = [-1] * scenario_count
    for node in nodes:
        if node.actor is not None:
            assert node.public_id is not None
            if actor_by_public[node.public_id] not in (-1, node.actor):
                raise AssertionError("public scenario ID mapped to more than one actor")
            actor_by_public[node.public_id] = node.actor
    if any(actor < 0 for actor in actor_by_public):
        raise AssertionError("public tree did not cover every dense scenario ID")
    return tuple(nodes), root, tuple(actor_by_public)


class MultiwayResponseValidator:
    """Finite split-sample unilateral-response audit for exact N=2..8 policies.

    The public FOLD/STAY tree is enumerated exactly for every sampled chance deal;
    opponent actions are integrated using their mixed policy probabilities rather
    than sampled. During the learn block, both counterfactual actions are valued
    at every reached exact information set. A deterministic unilateral response
    is then evaluated on an independent holdout block.

    Each player acts at most once in Pot Fold. Therefore, at one of that player's
    information sets, choosing FOLD or STAY can use the already-computed fixed-
    opponent child value directly. This gives a finite best-response estimate
    without card abstraction and without an inner action Monte Carlo.
    """

    def __init__(
        self,
        *,
        num_players: int,
        flop: Sequence[Card],
        policy: Mapping[int, tuple[float, float]],
        rake_pct: float = 0.0,
        rake_cap: float | None = None,
        seed: int = 1,
    ) -> None:
        if not 2 <= num_players <= 8:
            raise ValueError("num_players must be between 2 and 8")
        if len(flop) != 3:
            raise ValueError("flop must contain exactly three cards")
        require_unique(flop)
        if not 0.0 <= rake_pct < 1.0:
            raise ValueError("rake_pct must be in [0, 1)")
        if rake_cap is not None and rake_cap < 0.0:
            raise ValueError("rake_cap must be non-negative")

        self.num_players = num_players
        self.flop = tuple(flop)
        self.policy = dict(policy)
        self.rake_pct = float(rake_pct)
        self.rake_cap = rake_cap
        self.seed = int(seed)
        self.rng = random.Random(self.seed)

        self.exact_index = ExactFlopHoleIndex.build(self.flop)
        self.hole_state_count = len(self.exact_index)
        self.public_scenarios = decision_scenario_count(num_players)
        self.expected_infosets = self.hole_state_count * self.public_scenarios

        expected_keys = set(range(self.expected_infosets))
        supplied_keys = set(self.policy)
        missing = expected_keys - supplied_keys
        extra = supplied_keys - expected_keys
        if missing:
            raise ValueError(f"policy missing {len(missing)} exact infosets")
        if extra:
            raise ValueError(f"policy has {len(extra)} unexpected infosets")

        excluded = set(self.flop)
        self._deck = tuple(card for card in full_deck() if card not in excluded)
        raw_hole_to_state_id: dict[tuple[Card, Card], int] = {}
        for hole in combinations(self._deck, 2):
            raw = tuple(sorted(hole))
            raw_hole_to_state_id[raw] = self.exact_index.state_id(self.flop, hole)
        self._raw_hole_to_state_id = raw_hole_to_state_id

        self.nodes, self.root, self.actor_by_public = _build_public_tree(num_players)
        self._all_mask = (1 << num_players) - 1

    def _sample(self) -> tuple[tuple[tuple[Card, Card], ...], Card, Card]:
        need = 2 * self.num_players + 2
        cards = self.rng.sample(self._deck, need)
        holes = []
        pos = 0
        for _ in range(self.num_players):
            holes.append(tuple(sorted((cards[pos], cards[pos + 1]))))
            pos += 2
        return tuple(holes), cards[pos], cards[pos + 1]  # type: ignore[return-value]

    def _terminal_into(
        self,
        values: list[float],
        node_index: int,
        node: PublicTreeNode,
        ranks: tuple[tuple[int, ...], ...],
    ) -> None:
        n = self.num_players
        active_mask = self._all_mask ^ node.folded_mask
        active = [p for p in range(n) if active_mask & (1 << p)]
        if not active:
            raise AssertionError("Pot Fold terminal cannot have zero active players")

        if len(active) == 1:
            winners = (active[0],)
        else:
            best = max(ranks[p] for p in active)
            winners = tuple(p for p in active if ranks[p] == best)

        stayers = node.stayed_mask.bit_count()
        gross = float(n * (1 + stayers))
        rake = gross * self.rake_pct
        if self.rake_cap is not None:
            rake = min(rake, self.rake_cap)
        payout_each = (gross - rake) / len(winners)
        winner_set = set(winners)

        base = node_index * n
        for p in range(n):
            contribution = 1.0 + (float(n) if node.stayed_mask & (1 << p) else 0.0)
            payout = payout_each if p in winner_set else 0.0
            values[base + p] = payout - contribution

    def _fill_profile(
        self,
        *,
        holes: tuple[tuple[Card, Card], ...],
        turn: Card,
        river: Card,
        values: list[float],
        p_stay_by_node: list[float],
    ) -> tuple[tuple[int, ...], tuple[tuple[int, ...], ...]]:
        n = self.num_players
        board = self.flop + (turn, river)
        hole_ids = tuple(self._raw_hole_to_state_id[hole] for hole in holes)
        ranks = tuple(evaluate_seven(hole + board).as_tuple() for hole in holes)

        for idx, node in enumerate(self.nodes):
            base = idx * n
            if node.terminal:
                self._terminal_into(values, idx, node, ranks)
                continue

            assert node.actor is not None and node.public_id is not None
            assert node.fold_child is not None and node.stay_child is not None
            actor = node.actor
            key = node.public_id * self.hole_state_count + hole_ids[actor]
            p_stay = self.policy[key][1]
            p_stay_by_node[idx] = p_stay
            fold_base = node.fold_child * n
            stay_base = node.stay_child * n
            p_fold = 1.0 - p_stay
            for p in range(n):
                values[base + p] = p_fold * values[fold_base + p] + p_stay * values[stay_base + p]

        return hole_ids, ranks

    def _fill_reach(self, p_stay_by_node: list[float], reach: list[float]) -> None:
        reach[self.root] = 1.0
        for idx in range(len(self.nodes) - 1, -1, -1):
            node = self.nodes[idx]
            if node.terminal:
                continue
            assert node.fold_child is not None and node.stay_child is not None
            r = reach[idx]
            p_stay = p_stay_by_node[idx]
            reach[node.fold_child] = r * (1.0 - p_stay)
            reach[node.stay_child] = r * p_stay

    def validate(self, *, learn_samples: int, eval_samples: int) -> MultiwayResponseReport:
        if learn_samples <= 0 or eval_samples <= 0:
            raise ValueError("learn_samples and eval_samples must be positive")

        n = self.num_players
        h = self.hole_state_count
        node_count = len(self.nodes)
        values = [0.0] * (node_count * n)
        p_stay_by_node = [0.0] * node_count
        reach = [0.0] * node_count

        weight_sum = [0.0] * self.expected_infosets
        fold_value_sum = [0.0] * self.expected_infosets
        stay_value_sum = [0.0] * self.expected_infosets

        for _ in range(learn_samples):
            holes, turn, river = self._sample()
            hole_ids, _ = self._fill_profile(
                holes=holes,
                turn=turn,
                river=river,
                values=values,
                p_stay_by_node=p_stay_by_node,
            )
            self._fill_reach(p_stay_by_node, reach)

            for idx, node in enumerate(self.nodes):
                if node.terminal:
                    continue
                assert node.actor is not None and node.public_id is not None
                assert node.fold_child is not None and node.stay_child is not None
                actor = node.actor
                r = reach[idx]
                if r <= 0.0:
                    continue
                key = node.public_id * h + hole_ids[actor]
                weight_sum[key] += r
                fold_value_sum[key] += r * values[node.fold_child * n + actor]
                stay_value_sum[key] += r * values[node.stay_child * n + actor]

        br_stay = [False] * self.expected_infosets
        br_stay_states = [0] * n
        unreachable = [0] * n
        for key in range(self.expected_infosets):
            public_id, _hole_id = divmod(key, h)
            actor = self.actor_by_public[public_id]
            w = weight_sum[key]
            if w > 0.0:
                choose_stay = stay_value_sum[key] > fold_value_sum[key]
            else:
                unreachable[actor] += 1
                choose_stay = self.policy[key][1] >= 0.5
            br_stay[key] = choose_stay
            if choose_stay:
                br_stay_states[actor] += 1

        profile_stats = [RunningStats() for _ in range(n)]
        gain_stats = [RunningStats() for _ in range(n)]
        total_gain_stats = RunningStats()

        for _ in range(eval_samples):
            holes, turn, river = self._sample()
            hole_ids, _ = self._fill_profile(
                holes=holes,
                turn=turn,
                river=river,
                values=values,
                p_stay_by_node=p_stay_by_node,
            )
            self._fill_reach(p_stay_by_node, reach)

            root_base = self.root * n
            br_ev = [0.0] * n

            # Every target player's decision histories are disjoint and their
            # prefix reach probabilities sum to one, except BTN's all-FOLD path,
            # which terminates before BTN acts and is added below.
            for idx, node in enumerate(self.nodes):
                r = reach[idx]
                if r <= 0.0:
                    continue
                if node.terminal:
                    if node.depth < n:
                        # Mechanical early terminal can only be the all-fold
                        # prefix before BTN. BTN receives that terminal utility
                        # without taking a decision.
                        br_ev[n - 1] += r * values[idx * n + (n - 1)]
                    continue

                assert node.actor is not None and node.public_id is not None
                assert node.fold_child is not None and node.stay_child is not None
                actor = node.actor
                key = node.public_id * h + hole_ids[actor]
                child = node.stay_child if br_stay[key] else node.fold_child
                br_ev[actor] += r * values[child * n + actor]

            total_gain = 0.0
            for p in range(n):
                profile_ev = values[root_base + p]
                gain = br_ev[p] - profile_ev
                # Small negative values can occur from floating-point summation;
                # retain them rather than clipping the measured statistic.
                profile_stats[p].add(profile_ev)
                gain_stats[p].add(gain)
                total_gain += gain
            total_gain_stats.add(total_gain)

        return MultiwayResponseReport(
            num_players=n,
            flop=tuple(str(card) for card in self.flop),  # type: ignore[arg-type]
            exact_hole_states=h,
            public_scenarios=self.public_scenarios,
            learn_samples=learn_samples,
            eval_samples=eval_samples,
            seed=self.seed,
            rake_pct=self.rake_pct,
            rake_cap=self.rake_cap,
            profile_ev=tuple(stats.estimate() for stats in profile_stats),
            unilateral_gain=tuple(stats.estimate() for stats in gain_stats),
            total_unilateral_gain=total_gain_stats.estimate(),
            br_stay_states=tuple(br_stay_states),
            unreachable_infosets=tuple(unreachable),
        )


def report_to_dict(report: MultiwayResponseReport) -> dict:
    return asdict(report)


def main() -> None:
    ap = argparse.ArgumentParser(description="Finite exact multiway unilateral-response validator")
    ap.add_argument("--players", type=int, required=True)
    ap.add_argument("--policy", required=True)
    ap.add_argument("--flop", default="Ah 7d 2c")
    ap.add_argument("--learn-samples", type=int, required=True)
    ap.add_argument("--eval-samples", type=int, required=True)
    ap.add_argument("--seed", type=int, default=9302026)
    ap.add_argument("--rake-pct", type=float, default=0.02)
    ap.add_argument("--rake-cap", type=float, default=None)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    policy = load_policy_csv(args.policy)
    validator = MultiwayResponseValidator(
        num_players=args.players,
        flop=parse_flop(args.flop),
        policy=policy,
        rake_pct=args.rake_pct,
        rake_cap=args.rake_cap,
        seed=args.seed,
    )
    report = validator.validate(
        learn_samples=args.learn_samples,
        eval_samples=args.eval_samples,
    )
    payload = report_to_dict(report)
    payload["validator_version"] = MULTIWAY_RESPONSE_VERSION
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
