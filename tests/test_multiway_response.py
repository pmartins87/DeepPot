import math

from deeppot.cards import Card
from deeppot.multiway_response import MultiwayResponseValidator, _build_public_tree
from deeppot.state_space import decision_scenario_count


def cards(text: str):
    return tuple(Card.parse(x) for x in text.split())


def test_public_tree_dense_actor_mapping_n3() -> None:
    nodes, root, actor_by_public = _build_public_tree(3)
    assert root == len(nodes) - 1
    assert actor_by_public == (0, 1, 1, 2, 2, 2)
    assert len(actor_by_public) == decision_scenario_count(3)


def test_multiway_response_smoke_n3() -> None:
    # Monotone flop keeps the exact state count small enough for a fast CI smoke.
    flop = cards("Ah 7h 2h")
    hole_states = 344
    expected = hole_states * decision_scenario_count(3)
    policy = {key: (0.5, 0.5) for key in range(expected)}
    validator = MultiwayResponseValidator(
        num_players=3,
        flop=flop,
        policy=policy,
        rake_pct=0.02,
        seed=123,
    )
    assert validator.hole_state_count == hole_states
    report = validator.validate(learn_samples=20, eval_samples=20)
    assert report.num_players == 3
    assert len(report.profile_ev) == 3
    assert len(report.unilateral_gain) == 3
    assert report.total_unilateral_gain.samples == 20
    for estimate in (*report.profile_ev, *report.unilateral_gain, report.total_unilateral_gain):
        assert math.isfinite(estimate.mean)
        assert math.isfinite(estimate.ci95_high)
