import math

from deeppot.economics import PotFoldEconomy
from deeppot.game import Action, PotFoldRules, PotFoldState


def test_true_hu_first_player_fold_button_wins_without_stay() -> None:
    rules = PotFoldRules(num_players=2, ante=12.0)
    state = PotFoldState.initial(rules).apply(Action.FOLD)
    assert state.is_terminal
    assert state.uncontested_winner == 1
    assert state.stay_count == 0
    assert math.isclose(state.gross_pot, 24.0)


def test_two_percent_rake_explains_hu_net_profit_observation() -> None:
    economy = PotFoldEconomy(num_players=2, ante=12.0, rake_pct=0.02)
    utilities = economy.terminal_utilities(stayed=(False, False), winners=(1,))
    assert math.isclose(economy.nominal_rake(0), 0.48)
    assert math.isclose(economy.net_terminal_pot(0), 23.52)
    assert math.isclose(utilities[0], -12.0)
    assert math.isclose(utilities[1], 11.52)
    assert math.isclose(sum(utilities), -0.48)
