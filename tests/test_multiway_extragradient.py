import math

from deeppot.cards import Card
from deeppot.multiway_extragradient import (
    _projected_step,
    estimate_conditional_advantages,
    refine_policy_extragradient,
)
from deeppot.multiway_response import MultiwayResponseValidator
from deeppot.state_space import decision_scenario_count


def cards(text: str):
    return tuple(Card.parse(x) for x in text.split())


def test_advantage_estimator_matches_direct_root_child_values() -> None:
    flop = cards("Ah 7h 2h")
    hole_states = 344
    expected = hole_states * decision_scenario_count(3)
    policy = {key: (0.57, 0.43) for key in range(expected)}
    samples = 60

    validator = MultiwayResponseValidator(
        num_players=3,
        flop=flop,
        policy=policy,
        rake_pct=0.02,
        seed=991,
    )
    advantages, report = estimate_conditional_advantages(validator, samples=samples)
    assert report.samples == samples
    assert report.reachable_infosets > 0

    manual = MultiwayResponseValidator(
        num_players=3,
        flop=flop,
        policy=policy,
        rake_pct=0.02,
        seed=991,
    )
    n = 3
    node_count = len(manual.nodes)
    values = [0.0] * (node_count * n)
    probs = [0.0] * node_count
    sums = {}
    counts = {}
    root = manual.nodes[manual.root]
    assert root.actor is not None and root.public_id is not None
    assert root.fold_child is not None and root.stay_child is not None

    for _ in range(samples):
        holes, turn, river = manual._sample()
        hole_ids, _ = manual._fill_profile(
            holes=holes,
            turn=turn,
            river=river,
            values=values,
            p_stay_by_node=probs,
        )
        key = root.public_id * manual.hole_state_count + hole_ids[root.actor]
        delta = (
            values[root.stay_child * n + root.actor]
            - values[root.fold_child * n + root.actor]
        )
        sums[key] = sums.get(key, 0.0) + delta
        counts[key] = counts.get(key, 0) + 1

    for key, total in sums.items():
        assert math.isclose(advantages[key], total / counts[key], rel_tol=1e-12, abs_tol=1e-12)


def test_projected_step_direction_and_radius() -> None:
    policy = {0: (0.5, 0.5), 1: (0.5, 0.5), 2: (0.5, 0.5)}
    out, mean_delta, max_delta = _projected_step(
        policy,
        [2.0, -1.0, 0.0],
        radius=0.10,
    )
    assert math.isclose(out[0][1], 0.60)
    assert math.isclose(out[1][1], 0.45)
    assert math.isclose(out[2][1], 0.50)
    assert max_delta <= 0.100000000001
    assert mean_delta > 0.0


def test_extragradient_one_round_preserves_exact_policy_simplexes() -> None:
    flop = cards("Ah 7h 2h")
    hole_states = 344
    expected = hole_states * decision_scenario_count(3)
    policy = {key: (0.5, 0.5) for key in range(expected)}

    refined, audit = refine_policy_extragradient(
        num_players=3,
        flop=flop,
        initial_policy=policy,
        rake_pct=0.02,
        rake_cap=None,
        rounds=1,
        predictor_samples_per_round=10,
        corrector_samples_per_round=10,
        initial_max_coordinate_radius=0.10,
        seed_base=4321,
    )
    assert len(audit) == 1
    assert set(refined) == set(policy)
    assert audit[0].corrector_max_abs_update <= 0.100000000001
    for p_fold, p_stay in refined.values():
        assert 0.0 <= p_fold <= 1.0
        assert 0.0 <= p_stay <= 1.0
        assert math.isclose(p_fold + p_stay, 1.0, abs_tol=1e-12)
