from deeppot.cards import Card, canonical_flop_hole_id, canonical_flop_id, enumerate_canonical_flops


def c(x: str) -> Card:
    return Card.parse(x)


def test_standard_nlhe_has_1755_flop_isomorphism_classes() -> None:
    assert len(enumerate_canonical_flops()) == 1755


def test_canonical_flop_invariant_to_suit_renaming() -> None:
    a = (c("Ah"), c("Kd"), c("2h"))
    b = (c("As"), c("Kc"), c("2s"))
    assert canonical_flop_id(a) == canonical_flop_id(b)


def test_flop_hole_canonicalization_preserves_suit_relationships() -> None:
    flop1 = (c("Ah"), c("Kh"), c("2c"))
    hole1 = (c("Qh"), c("Jd"))
    flop2 = (c("As"), c("Ks"), c("2d"))
    hole2 = (c("Qs"), c("Jc"))
    assert canonical_flop_hole_id(flop1, hole1) == canonical_flop_hole_id(flop2, hole2)
