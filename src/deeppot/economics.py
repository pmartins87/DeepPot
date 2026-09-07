from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence


@dataclass(frozen=True)
class PotFoldEconomy:
    """Pot Fold pot/rake model.

    Pot rake and player-attributed rakeback/PVI are deliberately separated.
    `num_players` means players dealt into the hand (and therefore paying ante).
    Units are arbitrary as long as ante and rake_cap use the same unit.
    """

    num_players: int
    ante: float
    rake_pct: float = 0.0
    rake_cap: Optional[float] = None

    def __post_init__(self) -> None:
        if not 2 <= self.num_players <= 8:
            raise ValueError("num_players must be between 2 and 8")
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
        return self.initial_pot

    def gross_terminal_pot(self, stayers: int) -> float:
        # Zero stayers is valid: all players before the final-position survivor
        # can fold, causing an uncontested terminal without an extra contribution.
        if not 0 <= stayers <= self.num_players:
            raise ValueError("stayers must be between 0 and num_players")
        return self.initial_pot * (1 + stayers)

    def nominal_rake(self, stayers: int) -> float:
        gross = self.gross_terminal_pot(stayers)
        rake = gross * self.rake_pct
        if self.rake_cap is not None:
            rake = min(rake, self.rake_cap)
        return rake

    def net_terminal_pot(self, stayers: int) -> float:
        return self.gross_terminal_pot(stayers) - self.nominal_rake(stayers)

    def contribution(self, stayed: bool) -> float:
        return self.ante + (self.continue_cost if stayed else 0.0)

    def terminal_utilities(
        self,
        *,
        stayed: Sequence[bool],
        winners: Sequence[int],
    ) -> tuple[float, ...]:
        if len(stayed) != self.num_players:
            raise ValueError("stayed length must equal num_players")
        winner_set = tuple(sorted(set(int(i) for i in winners)))
        if not winner_set:
            raise ValueError("at least one winner is required")
        if winner_set[0] < 0 or winner_set[-1] >= self.num_players:
            raise ValueError("winner index out of range")
        payout_each = self.net_terminal_pot(sum(bool(x) for x in stayed)) / len(winner_set)
        out = []
        for i in range(self.num_players):
            payout = payout_each if i in winner_set else 0.0
            out.append(payout - self.contribution(bool(stayed[i])))
        return tuple(out)


def break_even_equity_no_future_actions(
    *,
    pot_before_call: float,
    call_cost: float,
    rake_pct: float = 0.0,
    rake_cap: Optional[float] = None,
) -> float:
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
    if not 2 <= num_players <= 8:
        raise ValueError("num_players must be between 2 and 8")
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
