import math

from deeppot.cards import Card
from deeppot.multiway_ped import _sample_gap_and_gradient, refine_policy_ped
from deeppot.multiway_response import MultiwayResponseValidator
from deeppot.state_space import decision_scenario_count


def cards(text: str):
    return tuple(Card.parse(x) for x in text.split())


def uniform_policy(num_players: int, flop, p_stay: float = 0.43):
    probe = MultiwayResponseValidator(
        num_players=num_players,
        flop=flop,
        policy={
            key: (0.5, 0.5)
            for key in range(
                (344 if str(flop[0]) == "Ah" and str(flop[1]) == "7h" and str(flop[2]) == "2h" else 1)
                * decision_scenario_count(num_players)
            )
        },
        seed=1,
    )
    return {
        key: (1.0 - p_stay, p_stay)
        for key in range(probe.expected_infosets)
    }


def test_sample_ped_gradient_matches_finite_difference() -> None:
    flop = cards("Ah 7h 2h")
    hole_states = 344
    expected = hole_states * decision_scenario_count(3)
    policy = {key: (0.57, 0.43) for key in range(expected)}
    validator = MultiwayResponseValidator(
        num_players=3,
        flop=flop,
        policy=policy,
        rake_pct=0.02,
        seed=777,
    )
    holes, turn, river = validator._sample()
    br_stay = [(key % 3) != 0 for key in range(expected)]

    gap, gradient = _sample_gap_and_gradient(
        validator,
        br_stay=br_stay,
        holes=holes,
        turn=turn,
        river=river,
    )
    assert math.isfinite(gap)

    root = validator.nodes[validator.root]
    assert root.actor is not None and root.public_id is not None
    hole_id = validator._raw_hole_to_state_id[holes[root.actor]]
    key = root.public_id * validator.hole_state_count + hole_id
    analytic = gradient[key]

    eps = 1e-6

    def sample_gap_with_p(p_stay: float) -> float:
        perturbed = dict(policy)
        perturbed[key] = (1.0 - p_stay, p_stay)
        v = MultiwayResponseValidator(
            num_players=3,
            flop=flop,
            policy=perturbed,
            rake_pct=0.02,
            seed=1,
        )
        value, _ = _sample_gap_and_gradient(
            v,
            br_stay=br_stay,
            holes=holes,
            turn=turn,
            river=river,
        )
        return value

    numerical = (sample_gap_with_p(0.43 + eps) - sample_gap_with_p(0.43 - eps)) / (2.0 * eps)
    assert math.isclose(analytic, numerical, rel_tol=2e-6, abs_tol=2e-6)


def test_ped_one_round_preserves_exact_policy_simplexes() -> None:
    flop = cards("Ah 7h 2h")
    hole_states = 344
    expected = hole_states * decision_scenario_count(3)
    policy = {key: (0.5, 0.5) for key in range(expected)}

    refined, audit = refine_policy_ped(
        num_players=3,
        flop=flop,
        initial_policy=policy,
        rake_pct=0.02,
        rake_cap=None,
        rounds=1,
        br_samples_per_round=8,
        gradient_samples_per_round=8,
        initial_max_coordinate_step=0.10,
        seed_base=1234,
    )

    assert len(audit) == 1
    assert set(refined) == set(policy)
    assert audit[0].max_abs_probability_update <= 0.100000000001
    for p_fold, p_stay in refined.values():
        assert 0.0 <= p_fold <= 1.0
        assert 0.0 <= p_stay <= 1.0
        assert math.isclose(p_fold + p_stay, 1.0, abs_tol=1e-12)
