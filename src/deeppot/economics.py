from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PotFoldEconomy:
    """Minimal Pot Fold pot/rake model.

    This module deliberately models *pot rake* only. KKPoker PVI and rakeback are
    player-attributed external credits and belong in a separate reward model.

    Units are arbitrary as long as `ante` and `rake_cap` use the same unit.
    """

    num_players: int
    ante: float
    rake_pct: float = 0.0
    rake_cap: Optional[float] = None

    def __post_init__(self) -> None:
        if self.num_players < 2:
            raise ValueError("num_players must be >= 2")
        if self.ante <= 0:
            raise ValueError("ante must be > 0")
        if not 0.0 <= self.rake_pct < 1.0:
            raise ValueError("rake_pct must be in [0, 1)")
        if self.rake_cap is not None and self.rake_cap < 0:
            raise ValueError("rake_cap must be >= 0")

    @property
    def initial_pot(self) -> float:
        return self.num_players * self.ante

    @property
    def continue_cost(self) -> float:
        # Verified Pot Fold rule: each continue contribution equals the initial pot.
        return self.initial_pot

    def gross_terminal_pot(self, continuers: int) -> float:
        if not 1 <= continuers <= self.num_players:
            raise ValueError("continuers must be between 1 and num_players")
        return self.initial_pot * (1 + continuers)

    def nominal_rake(self, continuers: int) -> float:
        gross = self.gross_terminal_pot(continuers)
        rake = gross * self.rake_pct
        if self.rake_cap is not None:
            rake = min(rake, self.rake_cap)
        return rake

    def net_terminal_pot(self, continuers: int) -> float:
        return self.gross_terminal_pot(continuers) - self.nominal_rake(continuers)


def break_even_equity_no_future_actions(
    *,
    pot_before_call: float,
    call_cost: float,
    rake_pct: float = 0.0,
    rake_cap: Optional[float] = None,
) -> float:
    """Return the showdown equity required for a call to have EV=0.

    Assumptions:
    - no later player acts;
    - winner receives the terminal pot after nominal pot rake;
    - no side pots;
    - ties and rakeback/PVI are omitted;
    - caller's current call_cost is the only incremental investment.

    This function is an *economic probe*, not a full Pot Fold strategy solver.
    """

    if pot_before_call < 0:
        raise ValueError("pot_before_call must be >= 0")
    if call_cost <= 0:
        raise ValueError("call_cost must be > 0")
    if not 0.0 <= rake_pct < 1.0:
        raise ValueError("rake_pct must be in [0, 1)")
    if rake_cap is not None and rake_cap < 0:
        raise ValueError("rake_cap must be >= 0")

    gross = pot_before_call + call_cost
    rake = gross * rake_pct
    if rake_cap is not None:
        rake = min(rake, rake_cap)
    net_payout = gross - rake
    if net_payout <= 0:
        raise ValueError("net payout must be > 0")

    return call_cost / net_payout


def simple_threshold_after_prior_continuers(
    *,
    num_players: int,
    prior_continuers: int,
    rake_pct: float = 0.0,
    rake_cap_in_antes: Optional[float] = None,
) -> float:
    """Convenience threshold with ante normalized to 1.

    Before hero acts:
        initial pot = N antes
        each prior continuer has added another N antes
        hero call cost = N antes

    The function assumes no player acts after hero, so it is most directly useful
    for the final decision position in a given action history.
    """

    if num_players < 2:
        raise ValueError("num_players must be >= 2")
    if prior_continuers < 1:
        raise ValueError("prior_continuers must be >= 1")
    if prior_continuers >= num_players:
        raise ValueError("prior_continuers must be < num_players")

    ante = 1.0
    p0 = num_players * ante
    pot_before = p0 * (1 + prior_continuers)
    cap = None if rake_cap_in_antes is None else float(rake_cap_in_antes)
    return break_even_equity_no_future_actions(
        pot_before_call=pot_before,
        call_cost=p0,
        rake_pct=rake_pct,
        rake_cap=cap,
    )
