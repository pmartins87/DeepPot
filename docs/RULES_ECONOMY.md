# Pot Fold rules, economics, and AoF comparison

Reference date: 2026-09-07

## 1. Official KKPoker rules currently verified

Source: KKPoker official Pot Fold page, published 2026-09-03.

- Traditional NLH/PLO showdown rules remain in force.
- Every player posts an ante; no additional SB/BB blind is posted.
- Preflop action does not exist.
- The flop is dealt immediately.
- Action starts from the Small Blind position player.
- The fixed continue amount equals the **initial pot**.
- Players can continue for that amount or fold.
- After flop action ends, if at least two players remain, turn and river are dealt automatically; no further betting streets exist.

Official example: 3-handed, 3c ante each => initial pot 9c. SB contributes 9c, BB folds, BTN contributes 9c, final gross pot 27c before any rake.

## 2. Pot geometry

Let:

- `N` = number of players dealt in;
- `A` = ante per player;
- `P0 = N * A` = initial pot;
- `C = P0` = fixed Pot Fold continue cost;
- `K` = number of players who continue.

Ignoring exceptional stack/side-pot cases, gross terminal pot is:

`P_gross = P0 + K * P0 = (K + 1) * P0`

Therefore the strategic geometry is scale invariant before rake/caps: changing the absolute ante does not change the ratio between the fixed continue cost and the initial pot.

This is a useful contrast to standard cash poker and to AoF, where stack/blind ratio is a first-order strategic parameter.

## 3. Simple break-even equity probes

For a player who is deciding whether to contribute `C` to a current gross pot `B`, with no later players and a simple effective terminal rake fraction `r`, a two-outcome break-even equity probe is:

`q_BE = C / ((B + C) * (1 - r))`

This is only a local probe. The full equilibrium also contains fold equity, future-player decisions, card removal, conditional ranges, caps, rakeback/PVI, and multiway ties.

### Example: one prior continuer

`B = 2*P0`, `C = P0`.

- no rake: 33.333%
- 2% effective rake: 34.014%
- 2.5% effective rake: 34.188%
- 3.5% effective rake: 34.542%
- 5% effective rake: 35.088%

A 5% terminal rake therefore raises this simple threshold by about **1.75 percentage points** versus no rake.

### Example: two prior continuers

`B = 3*P0`, `C = P0`.

- no rake: 25.000%
- 5% effective rake: 26.316%

The rake penalty is material but not automatically fatal to a game in which opponents can make large binary-decision errors.

## 4. What is currently known about KKPoker rake

KKPoker's current general rake page states, among other existing formats:

- standard NLH: 5% with stake-dependent caps (3 BB at lower listed stakes; 2 BB at higher listed stakes);
- PLO4/PLO5/PLO6: commonly 5% with stake-dependent caps;
- AoF: 2%;
- no rake when the pot is <=5 BB;
- half of designated rake when the table has <=3 players;
- split pots are raked;
- Instant Rakeback applies.

However, that page has **not yet been updated with a Pot Fold-specific section**. Consequently, DeepPot must not hard-code 5%, 2.5%, or any inherited cap until verified.

## 5. Rakeback/PVI must be modeled separately

KKPoker's official PVI explanation attributes each player's rake according to money contributed and a dynamic PVI factor. Instant Rakeback then applies to the player's attributed rake.

That means a mathematically faithful DeepPot model should distinguish:

1. **pot rake** removed from the terminal pot;
2. **player-attributed rake** used by KKPoker for rewards;
3. **rakeback credit** returned externally to a player;
4. optional club/set-rakeback assumptions.

For early economic probes we may use an `effective_rake` approximation, but the official solver should keep these components separate whenever the necessary live data can be measured.

## 6. AoF versus Pot Fold

| Property | DeepKK / AoF | DeepPot / Pot Fold |
|---|---|---|
| Decision street | Preflop | Flop only |
| Public board at decision | None | 3 cards |
| Forced money | SB/BB | Equal ante for all |
| Main action | All-in or Fold | Initial-pot contribution or Fold |
| Later betting | None after all-in | None after flop decision |
| Turn/River | Automatic after all-ins | Automatic after flop action |
| State size | 169 preflop classes per scenario | Flop + exact/abstracted hole state per scenario |
| Position/history | Binary action tree | Binary action tree, highly reusable from AoF conceptually |
| Rake known today | 2% AoF table | Pot Fold-specific table not yet published on official rake page |
| Solver challenge | Small state, large chance simulation | Very large flop-conditioned information state |

The major advantage is that Pot Fold remains a **single-decision-street binary-action game**. This makes it far more solvable than unrestricted postflop NLH despite the much larger state space.

## 7. Initial viability conclusion

Pot Fold looks structurally attractive for a solver project because:

- every decision is constrained to two actions;
- turn/river have no strategic actions, only chance/showdown;
- each public flop defines an independent subgame, enabling parallel solve-by-flop;
- the format is new, making large human strategy errors plausible;
- opponent tendencies can be tracked in a compact action tree, similar in spirit to DeepKK.

The economic downside is also clear:

- Pot Fold always reaches the flop, so the usual `hand ends preflop => no rake` exemption is irrelevant;
- if Pot Fold inherits normal NLH/PLO rake, nominal rake is much higher than AoF's 2%;
- PVI can reduce the value of rakeback for strong winners;
- exact cap semantics on ante-only tables are currently unknown.

**Working verdict:** technically very promising and plausibly profitable, but profitability is not yet proven. The format should pass an economy gate based on actual Pot Fold rake/cap + measured pool errors before we commit heavy solver compute.

## 8. Solver architecture consequence

Do not model DeepPot as `169 hand classes x scenarios`.

Recommended decomposition:

1. canonicalize the public flop under suit isomorphism (standard NLH has 1,755 flop isomorphism classes);
2. within each canonical flop, represent legal hero hole-card states relative to that board;
3. solve the binary sequential game for every position/action history;
4. cache exact or sampled turn-river equity calculations;
5. parallelize canonical flops across CPU workers;
6. use abstraction only where validation proves it does not materially change action/EV;
7. refine near-indifferent states more heavily than clearly dominated states.
