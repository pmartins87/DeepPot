# Live Pot Fold observations — 2026-09-07

These observations were supplied from live KKPoker play/inspection and are treated as empirical evidence, not as official KKPoker documentation.

## Table/action semantics confirmed

- Pot Fold tables have up to **8 seats**.
- The table is often not full, so the solver/runtime must support dynamic player counts from 2 through 8.
- There are no practical SB/BB forced-blind roles in the Pot Fold economy; all dealt players pay the same ante.
- The **BTN acts last** in the flop decision order.
- If all players before the BTN fold, the BTN wins immediately without making the fixed STAY contribution.
- An uncontested pot is still raked.

### True HU observation

- 2 players.
- Ante = 12 each.
- Initial gross pot = 24.
- First/non-BTN player folds.
- BTN wins without an additional STAY contribution.
- Observed net result for BTN: +11.52 relative to the 12 ante already posted.

If the 11.52 figure is interpreted as **net stack profit after the BTN's own ante**, it is exactly consistent with a 2% deduction from the 24 gross pot:

- gross pot: 24.00
- 2% rake: 0.48
- pot returned: 23.52
- winner's net profit after own 12 ante: 11.52

This is strong evidence for a 2% component, but is not sufficient by itself to freeze the full Pot Fold rake schedule.

## Additional payout observations

Two other reported gross-to-winner figures are:

| Gross pot | Winner received | Difference | Effective deduction |
|---:|---:|---:|---:|
| 84.00 | 81.12 | 2.88 | 3.428571% |
| 45.00 | 43.38 | 1.62 | 3.600000% |

These do **not** fit a simple uncapped 2% pot-rake model if the gross and received figures are directly comparable. They may indicate another fee component, a different rake schedule/cap, a display/accounting convention, or missing hand context.

Therefore DeepPot must keep rake parameterized and must not hard-code one global rate yet.

## Information that would resolve the remaining economic ambiguity later

For any future hand sample, record when convenient:

- number of players dealt in;
- ante;
- sequence of FOLD/STAY actions;
- gross terminal pot shown before deduction, if visible;
- amount awarded to the winner(s);
- any separate rake/fee/jackpot line in hand history;
- whether the amount quoted is total pot award or net stack change;
- any rakeback/EXP credit associated with the hand.

These details are useful but are **not a blocker for base-solver engineering** because the economy layer is parameterized and the strategy can be regenerated once the exact schedule is frozen.
