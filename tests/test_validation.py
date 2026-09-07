from deeppot.validation import build_consensus, compare_policies


def test_identical_policies_are_stable() -> None:
    p = {"a": (0.2, 0.8), "b": (0.9, 0.1)}
    pair = compare_policies(1, p, 2, p)
    assert pair.mean_abs_diff_stay == 0.0
    assert pair.greedy_agreement == 1.0
    _, consensus = build_consensus({1: p, 2: p})
    assert consensus.stability_hint == "stable"


def test_different_policies_are_unstable() -> None:
    a = {"a": (0.0, 1.0), "b": (1.0, 0.0)}
    b = {"a": (1.0, 0.0), "b": (0.0, 1.0)}
    _, consensus = build_consensus({1: a, 2: b})
    assert consensus.stability_hint == "unstable"
