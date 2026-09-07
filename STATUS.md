# DeepPot Status

Reference date: 2026-09-07

## State

**P0 — Rules and economy gate: IN PROGRESS**

Repository initialized from an empty `main` branch.

### Confirmed from KKPoker official Pot Fold rules (2026-09-03)

- Pot Fold follows traditional NLH/PLO hand-ranking rules but changes the betting options.
- NLH deals two hole cards to each player.
- Every player pays an ante; SB/BB positions do not post blinds in addition to that ante.
- Preflop betting is skipped; the flop is dealt immediately.
- Flop action begins with the player in the Small Blind position and proceeds around the table.
- The fixed continue action is the initial-pot amount; players can otherwise fold.
- Once flop action is complete and at least two players remain, turn and river are dealt automatically and the best hand wins at showdown.
- KKPoker advertises Pot Fold for NLH and PLO; FLASH excluded.
- Straddle, Post Big Blind, Ante Up, Bomb Pot and EV Chop are unavailable on Pot Fold tables.
- Pot Fold does not count toward VPIP.

### Rake status

**Not frozen.** The KKPoker general rake page currently lists NLH/PLO/AoF/etc. but does not yet expose a Pot Fold-specific rake table.

Relevant existing official structures:

- standard NLH: commonly 5% with caps by stake;
- standard PLO: commonly 5% with caps by stake;
- AoF: 2%;
- general cash-game rule: no rake for pots <=5 BB; half designated rake when the table has <=3 players;
- Instant Rakeback: 5% to 50%, with dynamic PVI affecting player-attributed rake.

These values are **context only**, not yet asserted as the Pot Fold economy.

## Technical decision already made

DeepPot will reuse DeepKK's layered architecture:

`base solver -> immutable base policy -> tracker/opponent model -> exploit policies -> DLL/OpenPPL runtime -> safe fallback`

But the solver state cannot reuse DeepKK's 169 preflop classes. DeepPot requires a flop-conditioned state representation.

## Immediate blockers to close P0

1. Pot Fold lobby/table screenshot showing stake/ante, number of seats and rake/cap information if displayed.
2. One or more hand examples where early positions all fold, to confirm last-player terminal behavior.
3. Confirmation whether the general `<=3 players => half rake` rule is actually applied to Pot Fold.
4. Confirmation of Pot Fold rakeback/EXP behavior in the live client.

## Next implementation target

P1 game kernel + P2 canonical flop/equity prototype can proceed in parallel because both are parameterized. Publication of an official strategy remains blocked until P0's economy is confirmed.
