from deeppot.cards import Card
from deeppot.multiway_refine import refine_policy
from deeppot.multiway_response import MultiwayResponseValidator
from deeppot.state_space import decision_scenario_count


def cards(text: str):
    return tuple(Card.parse(x) for x in text.split())


def test_multiway_refine_is_finite_dense_and_deterministic() -> None:
    flop = cards("Ah 7h 2h")
    hole_states = 344
    expected = hole_states * decision_scenario_count(3)
    initial = {key: (0.5, 0.5) for key in range(expected)}

    kwargs = dict(
        num_players=3,
        flop=flop,
        initial_policy=initial,
        rake_pct=0.02,
        rake_cap=None,
        rounds=2,
        samples_per_round=10,
        prior_weight=4,
        seed_base=1234,
    )
    pa, aa = refine_policy(**kwargs)
    pb, ab = refine_policy(**kwargs)

    assert pa == pb
    assert aa == ab
    assert len(pa) == expected
    assert len(aa) == 2
    assert aa[0].alpha == 1 / 5
    assert aa[1].alpha == 1 / 6
    for key, (p_fold, p_stay) in pa.items():
        assert 0 <= key < expected
        assert 0.0 <= p_fold <= 1.0
        assert 0.0 <= p_stay <= 1.0
        assert abs(p_fold + p_stay - 1.0) < 1e-12

    # The refined output must remain acceptable to the exact validator.
    validator = MultiwayResponseValidator(
        num_players=3,
        flop=flop,
        policy=pa,
        rake_pct=0.02,
        seed=9,
    )
    assert validator.expected_infosets == expected
