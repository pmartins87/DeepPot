from deeppot.cards import Card
from deeppot.evaluator import evaluate_seven, showdown_winners
from deeppot.equity import exact_hu_equity_on_flop


def cards(s: str):
    return tuple(Card.parse(x) for x in s.split())


def test_evaluator_orders_straight_flush_over_quads() -> None:
    sf = evaluate_seven(cards("Ah Kh Qh Jh Th 2c 3d"))
    quads = evaluate_seven(cards("As Ac Ad Ah Kc 2d 3s"))
    assert sf > quads


def test_wheel_straight() -> None:
    wheel = evaluate_seven(cards("As 2c 3d 4h 5s Kc Qd"))
    six_high = evaluate_seven(cards("2s 3c 4d 5h 6s Kc Qd"))
    assert six_high > wheel


def test_exact_hu_flop_has_990_runouts() -> None:
    e = exact_hu_equity_on_flop(cards("Ah Ad"), cards("Kh Kd"), cards("2c 7s 9h"))
    assert e.total == 990
    assert 0.0 <= e.equity <= 1.0


def test_showdown_tie() -> None:
    board = cards("Ah Kh Qh Jh Th")
    hands = (cards("2c 3d"), cards("4c 5d"))
    assert showdown_winners(hands, board) == (0, 1)
