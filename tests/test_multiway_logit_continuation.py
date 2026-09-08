import math

from deeppot.cards import Card
from deeppot.multiway_fixed_corpus import build_fixed_corpus, corpus_sha256
from deeppot.multiway_logit_continuation import (
    _apply_target_logit_update,
    _estimate_target_advantages_on_corpus,
    _logistic,
    refine_policy_cyclic_logit_continuation,
)
from deeppot.multiway_response import MultiwayResponseValidator
from deeppot.state_space import decision_scenario_count


def cards(text: str):
    return tuple(Card.parse(x) for x in text.split())


def test_logistic_is_stable_and_monotone() -> None:
    assert _logistic(-100.0) == 0.0
    assert _logistic(100.0) == 1.0
    assert math.isclose(_logistic(0.0), 0.5, abs_tol=1e-15)
    assert _logistic(-1.0) < _logistic(0.0) < _logistic(1.0)


def test_fixed_corpus_target_advantages_are_deterministic() -> None:
    flop = cards("Ah 7h 2h")
    h = 344
    expected = h * decision_scenario_count(3)
    policy = {key: (0.55, 0.45) for key in range(expected)}
    v1 = MultiwayResponseValidator(num_players=3, flop=flop, policy=policy, rake_pct=0.02, seed=123)
    v2 = MultiwayResponseValidator(num_players=3, flop=flop, policy=policy, rake_pct=0.02, seed=123)
    c1 = build_fixed_corpus(v1, samples=24)
    c2 = build_fixed_corpus(v2, samples=24)
    assert corpus_sha256(c1) == corpus_sha256(c2)

    a1, r1, rep1 = _estimate_target_advantages_on_corpus(v1, c1, target_seat=2)
    a2, r2, rep2 = _estimate_target_advantages_on_corpus(v2, c2, target_seat=2)
    assert a1 == a2
    assert r1 == r2
    assert rep1 == rep2


def test_target_update_changes_only_requested_seat_and_preserves_simplex() -> None:
    flop = cards("Ah 7h 2h")
    h = 344
    expected = h * decision_scenario_count(3)
    policy = {key: (0.5, 0.5) for key in range(expected)}
    validator = MultiwayResponseValidator(num_players=3, flop=flop, policy=policy, rake_pct=0.02, seed=44)
    corpus = build_fixed_corpus(validator, samples=32)
    adv, reachable, _ = _estimate_target_advantages_on_corpus(validator, corpus, target_seat=1)
    updated, _, max_update = _apply_target_logit_update(
        validator,
        policy,
        adv,
        reachable,
        target_seat=1,
        temperature=0.08,
        damping=0.5,
    )
    assert max_update <= 0.25 + 1e-12
    changed = 0
    for key, value in updated.items():
        public_id, _ = divmod(key, h)
        actor = validator.actor_by_public[public_id]
        if actor != 1:
            assert value == policy[key]
        elif value != policy[key]:
            changed += 1
        assert 0.0 <= value[0] <= 1.0
        assert 0.0 <= value[1] <= 1.0
        assert math.isclose(value[0] + value[1], 1.0, abs_tol=1e-12)
    assert changed > 0


def test_short_continuation_is_deterministic_and_preserves_policy() -> None:
    flop = cards("Ah 7h 2h")
    h = 344
    expected = h * decision_scenario_count(3)
    policy = {key: (0.5, 0.5) for key in range(expected)}
    kwargs = dict(
        num_players=3,
        flop=flop,
        initial_policy=policy,
        rake_pct=0.02,
        rake_cap=None,
        temperatures=(0.08, 0.04),
        sweeps_per_temperature=1,
        damping=0.5,
        corpus_samples=16,
        corpus_seed=9876,
    )
    p1, h1, a1 = refine_policy_cyclic_logit_continuation(**kwargs)
    p2, h2, a2 = refine_policy_cyclic_logit_continuation(**kwargs)
    assert h1 == h2
    assert p1 == p2
    assert a1 == a2
    assert len(a1) == 2 * 1 * 3
    for p_fold, p_stay in p1.values():
        assert 0.0 <= p_fold <= 1.0
        assert 0.0 <= p_stay <= 1.0
        assert math.isclose(p_fold + p_stay, 1.0, abs_tol=1e-12)
