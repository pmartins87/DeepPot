from deeppot.cards import Card
from deeppot.solver import ChanceSampledCFR


def cards(s: str):
    return tuple(Card.parse(x) for x in s.split())


def test_hu_solver_smoke_is_reproducible() -> None:
    kwargs = dict(num_players=2, flop=cards("Ah 7d 2c"), rake_pct=0.02, seed=123)
    a = ChanceSampledCFR(**kwargs).solve(30).average_policy()
    b = ChanceSampledCFR(**kwargs).solve(30).average_policy()
    assert a == b
    assert a
    for strategy in a.values():
        assert abs(sum(strategy) - 1.0) < 1e-12


def test_eight_player_solver_smoke() -> None:
    result = ChanceSampledCFR(num_players=8, flop=cards("Qs Jh 4c"), seed=7).solve(2)
    assert result.nodes
