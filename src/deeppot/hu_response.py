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
from .economics import PotFoldEconomy
from .evaluator import showdown_winners
from .exact_index import ExactFlopHoleIndex


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

    def ci95(self) -> tuple[float, float]:
        half = 1.959963984540054 * self.std_error
        return self.mean - half, self.mean + half


@dataclass(frozen=True)
class MetricEstimate:
    mean: float
    std_error: float
    ci95_low: float
    ci95_high: float
    samples: int


@dataclass(frozen=True)
class HUResponseReport:
    flop: tuple[str, str, str]
    exact_hole_states: int
    learn_samples: int
    eval_samples: int
    seed: int
    rake_pct: float
    rake_cap: float | None
    player0_profile_ev: MetricEstimate
    player1_profile_ev: MetricEstimate
    player0_br_gain: MetricEstimate
    player1_br_gain: MetricEstimate
    nashconv_gain: MetricEstimate
    player0_br_stay_states: int
    player1_br_stay_states: int
    player0_unlearned_states: int
    player1_unreached_states: int
    strategic_card_abstraction: str = "none"
    exact_symmetry_reduction: str = "global_suit_isomorphism_only"
    response_method: str = "split_sample_holdout_unilateral_best_response"


def _estimate(stats: RunningStats) -> MetricEstimate:
    low, high = stats.ci95()
    return MetricEstimate(
        mean=stats.mean,
        std_error=stats.std_error,
        ci95_low=low,
        ci95_high=high,
        samples=stats.n,
    )


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


class HUResponseValidator:
    """Finite holdout estimator of unilateral response gain for a fixed HU policy.

    Pot Fold HU has one private decision per player: player 0 acts at the root;
    player 1 acts only after observing player 0 STAY. That makes a unilateral
    best response representable as one binary action per exact information set.

    The validator deliberately uses two independent sample blocks:

    1. learn block: chooses the deterministic best-response action per exact
       information set against the supplied fixed opponent policy;
    2. holdout block: evaluates profile EV and the learned unilateral deviations.

    This avoids evaluating a best response on the same chance samples used to
    choose it. The result is a finite response audit with a paired 95% CI, not a
    claim of infinite-precision exploitability.
    """

    def __init__(
        self,
        *,
        flop: Sequence[Card],
        policy: Mapping[int, tuple[float, float]],
        rake_pct: float = 0.0,
        rake_cap: float | None = None,
        seed: int = 1,
    ) -> None:
        if len(flop) != 3:
            raise ValueError("flop must contain exactly three cards")
        require_unique(flop)
        self.flop = tuple(flop)
        self.policy = dict(policy)
        self.seed = int(seed)
        self.rng = random.Random(self.seed)
        self.economy = PotFoldEconomy(
            num_players=2,
            ante=1.0,
            rake_pct=rake_pct,
            rake_cap=rake_cap,
        )
        self.exact_index = ExactFlopHoleIndex.build(self.flop)
        self.hole_state_count = len(self.exact_index)
        self._deck = tuple(card for card in full_deck() if card not in set(self.flop))

        mapping: dict[tuple[Card, Card], int] = {}
        for hole in combinations(self._deck, 2):
            raw = tuple(sorted(hole))
            mapping[raw] = self.exact_index.state_id(self.flop, hole)
        self._raw_hole_to_state_id = mapping

        expected_keys = set(range(2 * self.hole_state_count))
        missing = expected_keys - set(self.policy)
        extra = set(self.policy) - expected_keys
        if missing:
            raise ValueError(f"HU policy missing {len(missing)} exact infosets")
        if extra:
            raise ValueError(f"HU policy has {len(extra)} unexpected infosets")

        # Only three showdown payoff patterns exist in HU; precompute them.
        self._u_p0_fold = self.economy.terminal_utilities(
            stayed=(False, False), winners=(1,)
        )
        self._u_p0_stay_p1_fold = self.economy.terminal_utilities(
            stayed=(True, False), winners=(0,)
        )
        self._u_showdown_p0 = self.economy.terminal_utilities(
            stayed=(True, True), winners=(0,)
        )
        self._u_showdown_p1 = self.economy.terminal_utilities(
            stayed=(True, True), winners=(1,)
        )
        self._u_showdown_tie = self.economy.terminal_utilities(
            stayed=(True, True), winners=(0, 1)
        )

    def _sample(self) -> tuple[tuple[Card, Card], tuple[Card, Card], Card, Card]:
        cards = self.rng.sample(self._deck, 6)
        h0 = tuple(sorted((cards[0], cards[1])))
        h1 = tuple(sorted((cards[2], cards[3])))
        return h0, h1, cards[4], cards[5]

    def _showdown_utility(
        self,
        h0: tuple[Card, Card],
        h1: tuple[Card, Card],
        turn: Card,
        river: Card,
    ) -> tuple[float, float]:
        winners = showdown_winners((h0, h1), self.flop + (turn, river))
        if winners == (0,):
            return self._u_showdown_p0
        if winners == (1,):
            return self._u_showdown_p1
        if winners == (0, 1):
            return self._u_showdown_tie
        raise AssertionError(f"unexpected HU winners {winners}")

    def _p_stay(self, public_scenario_id: int, hole_id: int) -> float:
        key = public_scenario_id * self.hole_state_count + hole_id
        return self.policy[key][1]

    def validate(self, *, learn_samples: int, eval_samples: int) -> HUResponseReport:
        if learn_samples <= 0 or eval_samples <= 0:
            raise ValueError("learn_samples and eval_samples must be positive")

        h = self.hole_state_count

        # Player 0 root response values. Sampling conditional on h0 is already
        # correct, so unit weights are sufficient.
        p0_s_sum = [0.0] * h
        p0_count = [0] * h

        # Player 1 reaches its infoset only when player 0 stays. Weighting each
        # compatible h0 chance sample by player-0 STAY probability produces the
        # correct posterior after observing STAY.
        p1_s_weighted_sum = [0.0] * h
        p1_reach_weight = [0.0] * h

        for _ in range(learn_samples):
            h0, h1, turn, river = self._sample()
            id0 = self._raw_hole_to_state_id[h0]
            id1 = self._raw_hole_to_state_id[h1]
            p0_stay = self._p_stay(0, id0)
            p1_stay = self._p_stay(1, id1)
            u_ss = self._showdown_utility(h0, h1, turn, river)

            # P0's value if it deviates to STAY while P1 remains fixed.
            p0_s_value = (
                (1.0 - p1_stay) * self._u_p0_stay_p1_fold[0]
                + p1_stay * u_ss[0]
            )
            p0_s_sum[id0] += p0_s_value
            p0_count[id0] += 1

            # P1's FOLD value after P0 STAY is constant (-ante). Only STAY
            # requires a weighted posterior expectation over P0's signaling range.
            if p0_stay > 0.0:
                p1_s_weighted_sum[id1] += p0_stay * u_ss[1]
                p1_reach_weight[id1] += p0_stay

        p0_fold_value = self._u_p0_fold[0]
        p1_fold_value = self._u_p0_stay_p1_fold[1]

        p0_br_stay = [False] * h
        p1_br_stay = [False] * h
        p0_unlearned = 0
        p1_unreached = 0

        for hole_id in range(h):
            if p0_count[hole_id] > 0:
                mean_stay = p0_s_sum[hole_id] / p0_count[hole_id]
                p0_br_stay[hole_id] = mean_stay > p0_fold_value
            else:
                # This should be rare at planned validation sample sizes. Use the
                # supplied policy's greedy action and count it explicitly.
                p0_unlearned += 1
                p0_br_stay[hole_id] = self._p_stay(0, hole_id) >= 0.5

            if p1_reach_weight[hole_id] > 0.0:
                mean_stay = p1_s_weighted_sum[hole_id] / p1_reach_weight[hole_id]
                p1_br_stay[hole_id] = mean_stay > p1_fold_value
            else:
                # The infoset has zero estimated reach under P0's fixed policy.
                # Its action cannot change ex-ante EV on the learning sample.
                p1_unreached += 1
                p1_br_stay[hole_id] = self._p_stay(1, hole_id) >= 0.5

        p0_profile_stats = RunningStats()
        p1_profile_stats = RunningStats()
        p0_gain_stats = RunningStats()
        p1_gain_stats = RunningStats()
        nashconv_stats = RunningStats()

        for _ in range(eval_samples):
            h0, h1, turn, river = self._sample()
            id0 = self._raw_hole_to_state_id[h0]
            id1 = self._raw_hole_to_state_id[h1]
            p0_stay = self._p_stay(0, id0)
            p1_stay = self._p_stay(1, id1)
            u_ss = self._showdown_utility(h0, h1, turn, river)

            p0_after_stay = (
                (1.0 - p1_stay) * self._u_p0_stay_p1_fold[0]
                + p1_stay * u_ss[0]
            )
            p1_after_stay = (
                (1.0 - p1_stay) * self._u_p0_stay_p1_fold[1]
                + p1_stay * u_ss[1]
            )

            u0_profile = (
                (1.0 - p0_stay) * self._u_p0_fold[0]
                + p0_stay * p0_after_stay
            )
            u1_profile = (
                (1.0 - p0_stay) * self._u_p0_fold[1]
                + p0_stay * p1_after_stay
            )

            if p0_br_stay[id0]:
                u0_br = p0_after_stay
            else:
                u0_br = self._u_p0_fold[0]

            p1_after_stay_br = (
                u_ss[1] if p1_br_stay[id1] else self._u_p0_stay_p1_fold[1]
            )
            u1_br = (
                (1.0 - p0_stay) * self._u_p0_fold[1]
                + p0_stay * p1_after_stay_br
            )

            g0 = u0_br - u0_profile
            g1 = u1_br - u1_profile

            p0_profile_stats.add(u0_profile)
            p1_profile_stats.add(u1_profile)
            p0_gain_stats.add(g0)
            p1_gain_stats.add(g1)
            nashconv_stats.add(g0 + g1)

        return HUResponseReport(
            flop=tuple(str(card) for card in self.flop),  # type: ignore[arg-type]
            exact_hole_states=h,
            learn_samples=learn_samples,
            eval_samples=eval_samples,
            seed=self.seed,
            rake_pct=self.economy.rake_pct,
            rake_cap=self.economy.rake_cap,
            player0_profile_ev=_estimate(p0_profile_stats),
            player1_profile_ev=_estimate(p1_profile_stats),
            player0_br_gain=_estimate(p0_gain_stats),
            player1_br_gain=_estimate(p1_gain_stats),
            nashconv_gain=_estimate(nashconv_stats),
            player0_br_stay_states=sum(p0_br_stay),
            player1_br_stay_states=sum(p1_br_stay),
            player0_unlearned_states=p0_unlearned,
            player1_unreached_states=p1_unreached,
        )


def report_to_dict(report: HUResponseReport) -> dict:
    return asdict(report)


def main() -> None:
    ap = argparse.ArgumentParser(description="Finite HU unilateral-response validator")
    ap.add_argument("--policy", required=True)
    ap.add_argument("--flop", default="Ah 7d 2c")
    ap.add_argument("--learn-samples", type=int, default=250000)
    ap.add_argument("--eval-samples", type=int, default=250000)
    ap.add_argument("--seed", type=int, default=9102026)
    ap.add_argument("--rake-pct", type=float, default=0.02)
    ap.add_argument("--rake-cap", type=float, default=None)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    policy = load_policy_csv(args.policy)
    validator = HUResponseValidator(
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
    data = report_to_dict(report)
    text = json.dumps(data, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
