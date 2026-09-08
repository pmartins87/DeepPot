from __future__ import annotations

import pytest

from deeppot.cards import Card, enumerate_canonical_flops
from deeppot.fast_solver import FastChanceSampledCFR
from deeppot.solver import ChanceSampledCFR


def _cards_from_key(key):
    return tuple(Card(rank, suit) for rank, suit in key)


@pytest.mark.parametrize("n,flop_index,iterations", [(2, 17, 80), (5, 877, 40), (8, 1200, 20)])
def test_fast_solver_matches_reference_exactly(n: int, flop_index: int, iterations: int) -> None:
    flop_key = list(enumerate_canonical_flops())[flop_index]
    flop = _cards_from_key(flop_key)
    kwargs = dict(
        num_players=n,
        flop=flop,
        rake_pct=0.02,
        rake_cap=None,
        seed=123,
        cfr_plus=True,
        linear_average=True,
    )
    ref = ChanceSampledCFR(**kwargs)
    fast = FastChanceSampledCFR(**kwargs)

    ref_result = ref.solve(iterations)
    fast_result = fast.solve(iterations)

    assert ref_result.iterations == fast_result.iterations
    assert ref_result.hole_state_count == fast_result.hole_state_count
    assert ref_result.flop_key == fast_result.flop_key
    assert ref.rng.getstate() == fast.rng.getstate()
    assert ref.nodes.keys() == fast.nodes.keys()

    for key in ref.nodes:
        a = ref.nodes[key]
        b = fast.nodes[key]
        assert a.visits == b.visits
        assert a.regrets == b.regrets
        assert a.strategy_sum == b.strategy_sum


@pytest.mark.parametrize("n,flop_index", [(3, 321), (8, 877)])
def test_fast_solver_resume_matches_fast_uninterrupted(n: int, flop_index: int) -> None:
    flop_key = list(enumerate_canonical_flops())[flop_index]
    flop = _cards_from_key(flop_key)
    kwargs = dict(
        num_players=n,
        flop=flop,
        rake_pct=0.02,
        rake_cap=None,
        seed=123,
        cfr_plus=True,
        linear_average=True,
    )

    full = FastChanceSampledCFR(**kwargs)
    full.solve(60)

    split = FastChanceSampledCFR(**kwargs)
    split.solve(23)
    split.continue_solve(37, completed_iterations=23)

    assert full.rng.getstate() == split.rng.getstate()
    assert full.nodes.keys() == split.nodes.keys()
    for key in full.nodes:
        a = full.nodes[key]
        b = split.nodes[key]
        assert a.visits == b.visits
        assert a.regrets == b.regrets
        assert a.strategy_sum == b.strategy_sum
