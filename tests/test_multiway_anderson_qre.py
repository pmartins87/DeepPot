import math

from deeppot.cards import Card
from deeppot.multiway_anderson_qre import (
    _estimate_all_advantages_on_corpus,
    _vector_to_policy,
    refine_policy_anderson_qre,
)
from deeppot.multiway_fixed_corpus import build_fixed_corpus
from deeppot.multiway_logit_continuation import _estimate_target_advantages_on_corpus
from deeppot.multiway_response import MultiwayResponseValidator
from deeppot.state_space import decision_scenario_count


def cards(text: str):
    return tuple(Card.parse(x) for x in text.split())


def test_all_seat_operator_matches_independent_p4h_seat_passes() -> None:
    flop = cards("Ah 7h 2h")
    hole_states = 344
    expected = hole_states * decision_scenario_count(3)
    policy = {key: (0.57, 0.43) for key in range(expected)}
    validator = MultiwayResponseValidator(
        num_players=3,
        flop=flop,
        policy=policy,
        rake_pct=0.02,
        seed=123,
    )
    corpus = build_fixed_corpus(validator, samples=32)
    all_adv, all_reach = _estimate_all_advantages_on_corpus(validator, corpus)

    for seat in range(3):
        seat_adv, seat_reach, _ = _estimate_target_advantages_on_corpus(
            validator,
            corpus,
            target_seat=seat,
        )
        for key in range(expected):
            public_id, _ = divmod(key, hole_states)
            if validator.actor_by_public[public_id] != seat:
                continue
            assert all_reach[key] == seat_reach[key]
            assert math.isclose(all_adv[key], seat_adv[key], rel_tol=0.0, abs_tol=1e-12)


def test_vector_to_policy_preserves_binary_simplex() -> None:
    policy = _vector_to_policy([-0.5, 0.2, 1.4])
    assert policy[0] == (1.0, 0.0)
    assert policy[1] == (0.8, 0.2)
    assert policy[2] == (0.0, 1.0)
    for p_fold, p_stay in policy.values():
        assert 0.0 <= p_fold <= 1.0
        assert 0.0 <= p_stay <= 1.0
        assert math.isclose(p_fold + p_stay, 1.0, abs_tol=1e-12)


def test_one_iteration_is_deterministic_and_preserves_policy_simplex() -> None:
    flop = cards("Ah 7h 2h")
    hole_states = 344
    expected = hole_states * decision_scenario_count(3)
    policy = {key: (0.5, 0.5) for key in range(expected)}

    kwargs = dict(
        num_players=3,
        flop=flop,
        initial_policy=policy,
        rake_pct=0.02,
        rake_cap=None,
        temperatures=(0.16,),
        iterations_per_temperature=1,
        memory=5,
        ridge=1e-8,
        anderson_mix=0.50,
        corpus_samples=16,
        corpus_seed=9912026,
    )
    refined_a, hash_a, audit_a = refine_policy_anderson_qre(**kwargs)
    refined_b, hash_b, audit_b = refine_policy_anderson_qre(**kwargs)

    assert hash_a == hash_b
    assert refined_a == refined_b
    assert audit_a == audit_b
    assert len(audit_a) == 1
    assert audit_a[0].memory_used == 0
    assert audit_a[0].reachable_infosets > 0
    for p_fold, p_stay in refined_a.values():
        assert 0.0 <= p_fold <= 1.0
        assert 0.0 <= p_stay <= 1.0
        assert math.isclose(p_fold + p_stay, 1.0, abs_tol=1e-12)
