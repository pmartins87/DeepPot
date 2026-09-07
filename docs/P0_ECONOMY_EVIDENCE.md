# P0 Pot Fold economy evidence

Reference date: 2026-09-07

This file is the finite evidence ledger for the Base-v1 economy freeze. The roadmap permits at most **12 clean live payout observations** if KKPoker does not publish a Pot-Fold-specific rake schedule.

## Official evidence

### Pot Fold rules

KKPoker's official Pot Fold rules page (published 2026-09-03):

- https://kkpoker.world/how-to-play/pot-fold/
- states that Pot Fold follows traditional NLH/PLO rules except for the betting options;
- all dealt players pay an ante;
- preflop is skipped;
- the flop has one FOLD or pot-sized continue decision street;
- turn/river are dealt automatically when at least two players remain.

The page does **not** state a Pot-Fold-specific rake percentage or cap.

### General KKPoker rake page

KKPoker's official Games & Rake Info page:

- https://kkpoker.net/how-to-play/rake-information/
- states that most game rake is between 2% and 5%;
- standard NLH is listed at 5% with stake-dependent caps;
- standard cash games list half designated rake when the table has 3 or fewer players;
- AOF has its own separate rake section;
- as of the reference date, the table of contents and rake tables do **not** contain a Pot Fold section.

Therefore DeepPot must not silently assume that Pot Fold inherits the standard NLH rake table. The live observations below also do not all fit one simple uncapped standard-NLH percentage.

## Live observations — 3 of maximum 12

### Observation 1 — true HU, uncontested

User report:

- 2 dealt players;
- ante = 12 each;
- first actor folds;
- BTN wins automatically without paying STAY;
- BTN reported net profit = 11.52.

Mechanical interpretation:

- gross pot = 24;
- if 11.52 is net stack profit, total returned to BTN = 12 + 11.52 = 23.52;
- deduction = 24 - 23.52 = 0.48;
- effective pot deduction = **2.000000%**.

This is strong evidence for a 2% pot deduction in this exact geometry, but it does not yet establish a universal Pot Fold rake rule.

### Observation 2

User report:

- gross/reference pot = 84;
- winner received = 81.12.

Calculation:

- deduction = 2.88;
- effective deduction = **3.428571%**.

Player count, ante, STAY sequence, table stake/cap unit and whether the displayed amount is gross award or net stack change were not recorded. Therefore this observation cannot yet identify the formula.

### Observation 3

User report:

- gross/reference pot = 45;
- winner received = 43.38.

Calculation:

- deduction = 1.62;
- effective deduction = **3.600000%**.

Player count, ante, STAY sequence, table stake/cap unit and whether the displayed amount is gross award or net stack change were not recorded. Therefore this observation cannot yet identify the formula.

## Current conclusion

**P0 economy remains UNFROZEN.**

Engineering/calibration may use the explicit provisional profile `provisional-2pct`, but the all-1,755-flop P5 production solve must not start until the live/official economy profile is frozen.

## Remaining finite collection allowance

Maximum additional clean live observations: **9**.

For each useful observation record exactly:

`players dealt | ante | table stake/label | FOLD/STAY sequence | gross terminal pot | amount awarded | net stack change if visible | separate rake/fee line if visible | jackpot opt-in/fee if relevant`

Prefer observations that vary player count and number of STAY actions. Stop collection immediately if an official Pot-Fold-specific rake schedule becomes available and is sufficient to freeze the production economy.
