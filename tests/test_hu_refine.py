from deeppot.cards import Card
from deeppot.exact_index import ExactFlopHoleIndex
from deeppot.hu_refine import refine_policy


def cards(text: str):
    return tuple(Card.parse(x) for x in text.split())


def uniform_policy(flop):
    h = len(ExactFlopHoleIndex.build(flop))
    return {key: (0.5, 0.5) for key in range(2 * h)}


def test_finite_refinement_is_reproducible_and_preserves_exact_keys() -> None:
    flop = cards("Ah 7h 2h")
    policy = uniform_policy(flop)
    kwargs = dict(
        flop=flop,
        initial_policy=policy,
        rake_pct=0.02,
        rake_cap=None,
        rounds=2,
        samples_per_round=100,
        prior_weight=4,
        seed_base=777,
    )
    a, audit_a = refine_policy(**kwargs)
    b, audit_b = refine_policy(**kwargs)
    assert a == b
    assert audit_a == audit_b
    assert set(a) == set(policy)
    assert len(audit_a) == 2
    for p_fold, p_stay in a.values():
        assert 0.0 <= p_fold <= 1.0
        assert 0.0 <= p_stay <= 1.0
        assert abs(p_fold + p_stay - 1.0) < 1e-12
