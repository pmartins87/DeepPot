import math

from deeppot.game import Action, PotFoldRules, PotFoldState


def test_official_three_handed_example() -> None:
    rules = PotFoldRules(num_players=3, ante=0.03)
    s = PotFoldState.initial(rules)

    # SB stays/bets the initial pot (9c).
    s = s.apply(Action.STAY)
    assert s.to_act == 1
    assert math.isclose(s.gross_pot, 0.18)

    # BB folds.
    s = s.apply(Action.FOLD)
    assert s.to_act == 2
    assert math.isclose(s.gross_pot, 0.18)

    # BTN stays/calls 9c => 27c gross pot and automatic showdown.
    s = s.apply(Action.STAY)
    assert s.is_terminal
    assert s.showdown
    assert s.active_count == 2
    assert s.stay_count == 2
    assert math.isclose(s.gross_pot, 0.27)


def test_last_player_wins_without_extra_stay_contribution() -> None:
    rules = PotFoldRules(num_players=3, ante=1.0)
    s = PotFoldState.initial(rules)
    s = s.apply(Action.FOLD)
    s = s.apply(Action.FOLD)

    assert s.is_terminal
    assert s.uncontested_winner == 2
    assert s.stay_count == 0
    assert math.isclose(s.gross_pot, 3.0)


def test_stayer_wins_when_everyone_after_folds() -> None:
    rules = PotFoldRules(num_players=4, ante=1.0)
    s = PotFoldState.initial(rules)
    s = s.apply(Action.STAY)
    s = s.apply(Action.FOLD)
    s = s.apply(Action.FOLD)
    s = s.apply(Action.FOLD)

    assert s.is_terminal
    assert s.uncontested_winner == 0
    assert s.stay_count == 1
    assert math.isclose(s.gross_pot, 8.0)


def test_all_stay_reaches_showdown() -> None:
    rules = PotFoldRules(num_players=4, ante=1.0)
    s = PotFoldState.initial(rules)
    for _ in range(4):
        s = s.apply(Action.STAY)

    assert s.is_terminal
    assert s.showdown
    assert s.active_count == 4
    assert s.stay_count == 4
    assert math.isclose(s.gross_pot, 20.0)
