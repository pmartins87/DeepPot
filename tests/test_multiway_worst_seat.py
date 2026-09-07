import math

from deeppot.cards import Card
from deeppot.multiway_response import MultiwayResponseValidator
from deeppot.multiway_worst_seat import (
    _dual_exponentiated_step,
    _sample_seat_gaps_and_gradients,
    refine_policy_primal_dual_worst_seat,
)
from deeppot.state_space import decision_scenario_count


def cards(text: str):
    return tuple(Card.parse(x) for x in text.split())


def test_seat_specific_gap_gradients_match_finite_difference() -> None:
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

    gaps, gradients = _sample_seat_gaps_and_gradients(
        validator,
        br_stay=br_stay,
        holes=holes,
        turn=turn,
        river=river,
    )
    assert len(gaps) == 3
    assert all(math.isfinite(value) for value in gaps)

    root = validator.nodes[validator.root]
    assert root.actor is not None and root.public_id is not None
    hole_id = validator._raw_hole_to_state_id[holes[root.actor]]
    key = root.public_id * validator.hole_state_count + hole_id
    eps = 1e-6

    def gaps_with_p(p_stay: float):
        perturbed = dict(policy)
        perturbed[key] = (1.0 - p_stay, p_stay)
        v = MultiwayResponseValidator(
            num_players=3,
            flop=flop,
            policy=perturbed,
            rake_pct=0.02,
            seed=1,
        )
        values, _ = _sample_seat_gaps_and_gradients(
            v,
            br_stay=br_stay,
            holes=holes,
            turn=turn,
            river=river,
        )
        return values

    plus = gaps_with_p(0.43 + eps)
    minus = gaps_with_p(0.43 - eps)
    for seat in range(3):
        numerical = (plus[seat] - minus[seat]) / (2.0 * eps)
        analytic = gradients[seat].get(key, 0.0)
        assert math.isclose(analytic, numerical, rel_tol=3e-6, abs_tol=3e-6)


def test_dual_step_remains_strict_probability_simplex_and_favors_worst_gap() -> None:
    weights = (1 / 3, 1 / 3, 1 / 3)
    gaps = (0.01, 0.07, 0.03)
    updated = _dual_exponentiated_step(weights, gaps, 0.5)
    assert all(value > 0.0 for value in updated)
    assert math.isclose(sum(updated), 1.0, abs_tol=1e-12)
    assert updated[1] > updated[2] > updated[0]


def test_one_primal_dual_round_preserves_policy_and_dual_simplexes() -> None:
    flop = cards("Ah 7h 2h")
    hole_states = 344
    expected = hole_states * decision_scenario_count(3)
    policy = {key: (0.5, 0.5) for key in range(expected)}

    refined, seat_weights, audit = refine_policy_primal_dual_worst_seat(
        num_players=3,
        flop=flop,
        initial_policy=policy,
        rake_pct=0.02,
        rake_cap=None,
        rounds=1,
        br_samples_per_stage=8,
        gradient_samples_per_stage=8,
        initial_primal_radius=0.05,
        initial_dual_radius=0.50,
        seed_base=1234,
    )

    assert len(audit) == 1
    assert set(refined) == set(policy)
    assert audit[0].predictor_max_abs_probability_update <= 0.050000000001
    assert audit[0].corrector_max_abs_probability_update <= 0.050000000001
    for p_fold, p_stay in refined.values():
        assert 0.0 <= p_fold <= 1.0
        assert 0.0 <= p_stay <= 1.0
        assert math.isclose(p_fold + p_stay, 1.0, abs_tol=1e-12)
    assert all(weight > 0.0 for weight in seat_weights)
    assert math.isclose(sum(seat_weights), 1.0, abs_tol=1e-12)
