from deeppot.cards import Card
from deeppot.exact_index import ExactFlopHoleIndex
from deeppot.hu_response import HUResponseValidator


def cards(text: str):
    return tuple(Card.parse(x) for x in text.split())


def full_hu_policy(flop, p0_stay: float, p1_stay: float):
    h = len(ExactFlopHoleIndex.build(flop))
    policy = {}
    for hole_id in range(h):
        policy[hole_id] = (1.0 - p0_stay, p0_stay)
        policy[h + hole_id] = (1.0 - p1_stay, p1_stay)
    return policy


def test_hu_response_is_reproducible() -> None:
    flop = cards("Ah 7h 2h")
    policy = full_hu_policy(flop, 0.5, 0.5)
    kwargs = dict(flop=flop, policy=policy, rake_pct=0.02, seed=12345)
    a = HUResponseValidator(**kwargs).validate(learn_samples=100, eval_samples=100)
    b = HUResponseValidator(**kwargs).validate(learn_samples=100, eval_samples=100)
    assert a == b
    assert a.nashconv_gain.samples == 100
    assert a.exact_hole_states == 344


def test_hu_response_requires_complete_exact_policy() -> None:
    flop = cards("Ah 7h 2h")
    policy = full_hu_policy(flop, 0.5, 0.5)
    policy.pop(0)
    try:
        HUResponseValidator(flop=flop, policy=policy)
    except ValueError as exc:
        assert "missing" in str(exc)
    else:
        raise AssertionError("incomplete HU policy must be rejected")
