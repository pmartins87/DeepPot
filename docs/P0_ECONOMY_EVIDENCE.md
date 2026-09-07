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
- AOF has its own separate rake section at 2%;
- as of the reference date, the table of contents and rake tables do **not** contain a Pot Fold section.

Therefore DeepPot must not silently assume that Pot Fold inherits the standard NLH rake table.

## Live observations — 3 of maximum 12

### Observation 1 — true HU, uncontested

User report:

- 2 dealt players;
- ante = 12 each;
- first actor folds;
- BTN wins automatically without paying STAY;
- BTN reported net profit = 11.52.

Mechanical interpretation:

- gross terminal pot = 24;
- total returned to BTN = own ante 12 + profit 11.52 = 23.52;
- deduction = 24 - 23.52 = 0.48;
- deduction/gross pot = **2.000000%**.

This also shows that Pot Fold does not simply inherit the general standard-NLH `<=3 players -> half designated rake` rule in the obvious way: the observed deduction is already 2% in true HU.

### Observations 2 and 3 — important semantic reconciliation

User wording was that in other situations the amount "would be 84" but the winner received 81.12, and "would be 45" but the winner received 43.38.

The earlier ledger treated 84 and 45 as **gross terminal pots**. That interpretation produced apparent rates of 3.4286% and 3.6%. It is not the only interpretation, and it is inconsistent with how observation 1 was reported as net profit.

If 84 and 45 are instead the winner's **pre-rake net win** (gross award minus that winner's own contributions), then both observations reconcile *exactly* with a 2% deduction from the gross terminal pot:

#### Observation 2

- pre-rake net win = 84;
- actual net win = 81.12;
- reduction in net win = 2.88;
- under a 2% gross-pot rake, implied gross terminal pot = `2.88 / 0.02 = 144`;
- implied winner contribution = `144 - 84 = 60`;
- post-rake net = `144 * 0.98 - 60 = 81.12` exactly.

The implied geometry is mechanically plausible for Pot Fold (for example a 4-player, ante-12 hand with two STAY contributions gives gross 144 and a STAYing winner contribution of 60), but that player-count/action geometry was not explicitly recorded and is therefore not promoted to observed fact.

#### Observation 3

- pre-rake net win = 45;
- actual net win = 43.38;
- reduction in net win = 1.62;
- under a 2% gross-pot rake, implied gross terminal pot = `1.62 / 0.02 = 81`;
- implied winner contribution = `81 - 45 = 36`;
- post-rake net = `81 * 0.98 - 36 = 43.38` exactly.

Again the implied geometry is mechanically plausible (for example a 3-player, ante-9 hand with two STAY contributions gives gross 81 and a STAYing winner contribution of 36), but the missing live metadata prevents treating that example geometry as fact.

## Current conclusion

The three user-reported payouts are now **mutually consistent with one simple rule: 2% rake on the gross terminal Pot Fold pot, including uncontested pots**. The previous apparent 3.43%/3.60% conflict came from treating net-win figures as gross pots.

This is strong enough to keep `provisional-2pct` as the sole engineering/calibration profile. It is **not yet enough to freeze P0 production economics**, because the Pot-Fold-specific cap (or evidence of no cap) is still unknown and observations 2/3 lack their original player-count/action metadata.

The official KKPoker rake page still has no Pot Fold row as of 2026-09-07. Its AOF section lists 2% and no cap column, but that is supporting context only, not proof that Pot Fold inherits AOF economics.

## Remaining finite collection allowance

Maximum additional clean live observations: **9**, but we do not need to consume the allowance. A small number of clean observations can close P0 if they confirm the gross-pot 2% interpretation and expose any cap behavior.

For each useful observation record exactly:

`players dealt | ante | table stake/label | FOLD/STAY sequence | gross terminal pot | amount awarded | net stack change if visible | separate rake/fee line if visible`

Highest-value evidence now is:

1. one clean multiway hand where gross pot and winner contribution are both reconstructable, to confirm 2% gross-pot rake outside HU;
2. one comparatively large terminal pot at the intended Base-v1 stake, to reveal whether a cap binds.

Stop collection immediately once the economy profile is uniquely identified or if an official Pot-Fold-specific rake schedule is published.
