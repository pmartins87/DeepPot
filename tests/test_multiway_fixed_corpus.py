import math

from deeppot.cards import Card
from deeppot.multiway_fixed_corpus import (
    _estimate_fixed_stage,
    _learn_pure_best_responses_on_corpus,
    _smooth_worst_seat_weights,
    build_fixed_corpus,
    corpus_sha256,
    refine_policy_fixed_corpus,
)
from deeppot.multiway_response import MultiwayResponseValidator
from deeppot.state_space import decision_scenario_count


def cards(text: str):
    return tuple(Card.parse(x) for x in text.split())


def uniform_policy(hole_states: int, num_players: int = 3):
    expected = hole_states * decision_scenario_count(num_players)
    return {key: (0.5, 0.5) for key in range(expected)}


def test_fixed_corpus_is_reproducible_and_hash_stable() -> None:
    flop = cards("Ah 7h 2h")
    policy = uniform_policy(344)
    a = MultiwayResponseValidator(num_players=3, flop=flop, policy=policy, rake_pct=0.02, seed=4321)
    b = MultiwayResponseValidator(num_players=3, flop=flop, policy=policy, rake_pct=0.02, seed=4321)
    corpus_a = build_fixed_corpus(a, samples=32)
    corpus_b = build_fixed_corpus(b, samples=32)
    assert corpus_a == corpus_b
    assert corpus_sha256(corpus_a) == corpus_sha256(corpus_b)


def test_same_corpus_empirical_best_response_gaps_are_nonnegative() -> None:
    flop = cards("Ah 7h 2h")
    policy = uniform_policy(344)
    validator = MultiwayResponseValidator(
        num_players=3,
        flop=flop,
        policy=policy,
        rake_pct=0.02,
        seed=9876,
    )
    corpus = build_fixed_corpus(validator, samples=96)
    br_stay, _, _ = _learn_pure_best_responses_on_corpus(validator, corpus)
    assert len(br_stay) == validator.expected_infosets

    _gradients, report = _estimate_fixed_stage(
        num_players=3,
        flop=flop,
        policy=policy,
        rake_pct=0.02,
        rake_cap=None,
        corpus=corpus,
        smoothmax_beta=100.0,
    )
    assert report.negative_gap_count == 0
    assert all(gap >= -1e-10 for gap in report.seat_gaps)


def test_smooth_worst_seat_weights_form_simplex_and_favor_larger_gap() -> None:
    weights = _smooth_worst_seat_weights((0.01, 0.05, 0.03), beta=100.0)
    assert math.isclose(sum(weights), 1.0, abs_tol=1e-12)
    assert all(weight > 0.0 for weight in weights)
    assert weights[1] > weights[2] > weights[0]


def test_tiny_fixed_corpus_refinement_is_deterministic_and_preserves_simplex() -> None:
    flop = cards("Ah 7h 2h")
    policy = uniform_policy(344)
    kwargs = dict(
        num_players=3,
        flop=flop,
        initial_policy=policy,
        rake_pct=0.02,
        rake_cap=None,
        rounds=1,
        corpus_samples=16,
        corpus_seed=2468,
        initial_max_coordinate_radius=0.05,
        smoothmax_beta=100.0,
    )
    refined_a, hash_a, audit_a = refine_policy_fixed_corpus(**kwargs)
    refined_b, hash_b, audit_b = refine_policy_fixed_corpus(**kwargs)

    assert hash_a == hash_b
    assert refined_a == refined_b
    assert audit_a == audit_b
    assert len(audit_a) == 1
    assert audit_a[0].predictor_max_abs_probability_update <= 0.050000000001
    assert audit_a[0].corrector_max_abs_probability_update <= 0.050000000001
    for p_fold, p_stay in refined_a.values():
        assert 0.0 <= p_fold <= 1.0
        assert 0.0 <= p_stay <= 1.0
        assert math.isclose(p_fold + p_stay, 1.0, abs_tol=1e-12)
