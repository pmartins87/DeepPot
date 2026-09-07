import math

from deeppot.economics import (
    PotFoldEconomy,
    break_even_equity_no_future_actions,
    simple_threshold_after_prior_continuers,
)


def test_three_handed_official_example_geometry() -> None:
    econ = PotFoldEconomy(num_players=3, ante=0.03)
    assert math.isclose(econ.initial_pot, 0.09)
    assert math.isclose(econ.continue_cost, 0.09)
    assert math.isclose(econ.gross_terminal_pot(2), 0.27)


def test_one_prior_continuer_no_rake_is_one_third() -> None:
    q = simple_threshold_after_prior_continuers(
        num_players=3,
        prior_continuers=1,
        rake_pct=0.0,
    )
    assert math.isclose(q, 1.0 / 3.0, rel_tol=1e-12)


def test_one_prior_continuer_five_percent_rake() -> None:
    q = simple_threshold_after_prior_continuers(
        num_players=3,
        prior_continuers=1,
        rake_pct=0.05,
    )
    assert math.isclose(q, 1.0 / (3.0 * 0.95), rel_tol=1e-12)


def test_two_prior_continuers_five_percent_rake() -> None:
    q = simple_threshold_after_prior_continuers(
        num_players=4,
        prior_continuers=2,
        rake_pct=0.05,
    )
    assert math.isclose(q, 1.0 / (4.0 * 0.95), rel_tol=1e-12)


def test_rake_cap_changes_threshold() -> None:
    uncapped = break_even_equity_no_future_actions(
        pot_before_call=6.0,
        call_cost=3.0,
        rake_pct=0.05,
    )
    capped = break_even_equity_no_future_actions(
        pot_before_call=6.0,
        call_cost=3.0,
        rake_pct=0.05,
        rake_cap=0.10,
    )
    assert capped < uncapped
