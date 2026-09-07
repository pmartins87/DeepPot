from deeppot.cards import parse_cards
from deeppot.exact_index import ExactFlopHoleIndex


def test_representative_exact_hole_counts() -> None:
    # Distinct-rank rainbow flop: no non-trivial suit stabilizer remains.
    rainbow = ExactFlopHoleIndex.build(parse_cards(["Ah", "7d", "2c"]))
    assert len(rainbow) == 1176
    assert rainbow.stabilizer_size == 1

    # Distinct-rank monotone flop: the three unused suits remain interchangeable.
    monotone = ExactFlopHoleIndex.build(parse_cards(["Ah", "7h", "2h"]))
    assert len(monotone) == 344
    assert monotone.stabilizer_size == 6

    # Distinct-rank two-tone flop.
    twotone = ExactFlopHoleIndex.build(parse_cards(["Ah", "7h", "2c"]))
    assert len(twotone) == 721
    assert twotone.stabilizer_size == 2

    # Paired rainbow structure.
    paired = ExactFlopHoleIndex.build(parse_cards(["Ah", "Ad", "2c"]))
    assert len(paired) == 744
    assert paired.stabilizer_size == 2


def test_suit_relabeling_maps_to_same_dense_state() -> None:
    flop_a = parse_cards(["Ah", "7d", "2c"])
    hole_a = parse_cards(["Kh", "Qh"])

    # Global suit relabeling h<->s, d<->c. Strategically identical state.
    flop_b = parse_cards(["As", "7c", "2d"])
    hole_b = parse_cards(["Ks", "Qs"])

    index = ExactFlopHoleIndex.build(flop_a)
    assert index.state_id(flop_a, hole_a) == index.state_id(flop_b, hole_b)


def test_strategically_distinct_same_169_class_remains_distinct() -> None:
    flop = parse_cards(["Qh", "7h", "2c"])
    index = ExactFlopHoleIndex.build(flop)

    # Both are AKs in the 169 preflop representation, but only AhKh has the
    # front-door heart flush draw on this flop. The exact index must not merge.
    heart_aks = parse_cards(["Ah", "Kh"])
    club_aks = parse_cards(["Ac", "Kc"])
    assert index.state_id(flop, heart_aks) != index.state_id(flop, club_aks)
