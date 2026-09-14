# DeepPot rake / rakeback sensitivity — 2026-09-13

## Status of the 2% gross-rake assumption

The current production/training economy uses `rake_pct = 0.02` with no cap.

This **did not come from the OpenHoldem SEL2500 logs** and is not currently published in a Pot-Fold-specific KKPoker rake table.

It comes from the prior live-evidence ledger in `docs/P0_ECONOMY_EVIDENCE.md`:

- one clean true-HU uncontested observation had 2 dealt players, ante 12 each, gross terminal pot 24, and the winner reported net profit 11.52;
- that implies 23.52 returned from a gross 24 pot, a deduction of 0.48 = exactly 2.00%;
- two additional user-reported payout examples are also exactly consistent with 2% of the gross terminal pot when their quoted amounts are interpreted as pre-rake net wins.

Therefore 2% remains the strongest current live model, but it is still tagged **provisional** because KKPoker has not published a Pot-Fold-specific rake row and the cap/no-cap behavior is not independently established.

The SEL2500 OpenHoldem logs do not contain a clean per-hand rake/payout field and include pot-scrape warnings, so they cannot independently identify the gross rake percentage.

## What the 940-hand session establishes directly

User-reported KKPoker UI totals for the same session:

- 940 hands;
- $6.96 rakeback;
- 50% nominal rakeback;
- $196.47 profit.

The log-derived Hero contribution estimate is approximately $993.60–$1,002.80 once the 46 hands without a DeepPot decision are bounded by their ante-only contribution.

The most robust directly observed quantity is therefore:

- cashback / Hero contribution ≈ **0.694%–0.700%**.

This quantity does **not** require knowing the gross rake percentage.

If gross rake is 2%, then translating that cashback rate through the KKPoker PVI allocation formula gives an effective relative-PVI factor near 0.69–0.70 and an equal-PVI-benchmark rakeback near 35% (`50% × 0.70`). That translation is conditional on the 2% gross-rake model; it must not be presented as an independently measured PVI.

## Conditional rakeback sensitivity audit

Audit basis:

- snapshot: `V2_SEL2500`;
- 12 deliberately difficult tasks: top 3 unstable flops for each N=5..8;
- 250 conditional chance samples per selected exact infoset;
- 50 marginal FOLD states (`p(STAY)` in [0.40, 0.50)) + 50 random FOLD states per task;
- opponent-card samples weighted by the prior public-history reach under the persisted CFR average policy;
- gross rake baseline: provisional 2%;
- nominal RB: 50%;
- empirical cashback sensitivity band: 0.60%, 0.70%, 0.80% of Hero contribution.

Center result (0.70% cashback / contribution):

- marginal FOLD: 4 / 357 eligible states crossed from FOLD-EV-best to STAY-EV-best = **1.120%**;
- random FOLD: 1 / 373 = **0.268%**;
- statistically confident reversals at this sample size: **0**.

Band:

- 0.60% cashback: marginal 0.840%, random 0.268%;
- 0.70% cashback: marginal 1.120%, random 0.268%;
- 0.80% cashback: marginal 1.120%, random 0.268%.

Interpretation: within a deliberately stress-selected set of unstable N5–N8 tasks, the empirically observed rebate is a small perturbation concentrated near action indifference. The evidence does **not** justify restarting the 635M-infoset CFR trajectory for rakeback. The final DeepKK-style EV/CI decision audit should, however, include the Hero cashback term so that genuinely marginal FOLD/STAY states are resolved using the user's observed economics.

## Training decision

Continue the existing 2%-gross-rake CFR trajectory selectively:

- source snapshot for instability: `V2_2000 -> V2_SEL2500`;
- select only tasks with `changed_pct > 2.0%`;
- selected tasks: 1,756 / 12,285;
- continue those tasks until `visit_min >= 3000`;
- do not alter source-locked mathematical files or reset any selected task state/RNG;
- after completion create `V2_SEL3000`, remeasure stability, and only then choose the next funnel / EV audit.

The final production policy should treat the gross-rake model and Hero rakeback as separate economic terms; do not replace 2% gross rake by a synthetic 1% or 1.3% net rake.
