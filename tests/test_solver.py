from deeppot.cards import Card
from deeppot.solver import ChanceSampledCFR


def cards(s: str):
    return tuple(Card.parse(x) for x in s.split())


def test_hu_solver_smoke_is_reproducible() -> None:
    kwargs = dict(num_players=2, flop=cards("Ah 7d 2c"), rake_pct=0.02, seed=123)
    ra = ChanceSampledCFR(**kwargs).solve(30)
    rb = ChanceSampledCFR(**kwargs).solve(30)
    a = ra.average_policy()
    b = rb.average_policy()
    assert a == b
    assert a
    assert ra.hole_state_count == 1176
    for key, strategy in a.items():
        assert isinstance(key, int)
        public_id, hole_id = ra.decode_infoset_key(key)
        assert public_id in (0, 1)
        assert 0 <= hole_id < 1176
        assert abs(sum(strategy) - 1.0) < 1e-12


def test_eight_player_solver_smoke() -> None:
    result = ChanceSampledCFR(num_players=8, flop=cards("Qs Jh 4c"), seed=7).solve(2)
    assert result.nodes
    for key in result.nodes:
        public_id, hole_id = result.decode_infoset_key(key)
        assert 0 <= public_id < 254
        assert 0 <= hole_id < result.hole_state_count
