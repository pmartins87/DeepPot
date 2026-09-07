# P4F — primal-dual worst-seat exploitability method reset

Reference date: 2026-09-07

Status at commit: **PROTOCOL FROZEN BEFORE P4F RESULTS**

## Why P4F is a new method rather than P4D/P4E tuning

P4D minimized an approximately uniform sum of unilateral deviation gains. It passed the N=3 monotone case but left one rainbow seat above the frozen 0.03-ante gate. P4E instead followed local own-action advantages through projected extragradient; the rainbow case left two seats above the gate.

The production gate is explicitly **worst-seat**: every seat must have unilateral-response upper <= 0.03 ante. P4F therefore changes the optimization target itself to

`min_policy max_seat E_seat(policy)`

where

`E_i = u_i(BR_i(policy_-i), policy_-i) - u_i(policy)`.

P4F uses a primal-dual mirror-prox approximation of that finite exact-state minimax objective. A dual simplex over seats automatically puts more weight on the currently harder seat instead of treating every seat uniformly.

## Exact-state constraints retained

- no strategic card abstraction;
- only true global suit-isomorphism reduction;
- exact public FOLD/STAY tree;
- every player's behavioral coordinate remains one exact `P(STAY) in [0,1]` simplex coordinate;
- original split-sample unilateral-best-response validator remains the release gate.

## Frozen N=3 viability cases

Run exactly two cases:

1. N=3 rainbow `Ah 7d 2c`;
2. N=3 monotone `Ah 7h 2h`.

No other texture is introduced in P4F N=3 viability.

## Frozen warm start

P4F starts from the already-defined P4D path, regenerated deterministically for each case:

1. exact CFR consensus: `250k x 3` seeds;
2. FP warm start: `32 x 50k`, prior weight 4;
3. PED warm start: 32 rounds, each `50k BR-learn + 50k gradient` samples, radius `0.10/sqrt(round)`.

P4F does **not** select a P4D checkpoint. It always receives the fixed final P4D policy.

## Frozen primal-dual mirror-prox stage

Exactly **32 rounds**.

Every round has two independent stages.

### Predictor stage

At the current `(policy, seat_weights)`:

- learn all seats' pure unilateral BRs from 50,000 chance samples;
- estimate every seat's unilateral deviation gap and every seat-specific policy gradient from an independent 50,000 chance samples;
- form the policy gradient as the dual-weighted sum of seat gradients;
- take one projected policy predictor step;
- take one exponentiated-gradient dual predictor step toward seats with larger estimated gaps.

### Corrector stage

At the predictor state:

- relearn all unilateral BRs from a fresh 50,000 samples;
- estimate gaps/seat gradients from another fresh 50,000 samples;
- compute the predictor dual-weighted policy gradient;
- correct the **original** policy and dual weights using those predictor-state estimates.

Thus each round consumes exactly 200,000 chance samples in four independent deterministic-seed blocks.

## Frozen steps

Policy maximum-coordinate radius:

`0.05 / sqrt(round)`

The weighted policy gradient is L-infinity normalized before the projected step, so no exact behavioral coordinate moves by more than that radius before clipping to `[0,1]`.

Dual seat-weight radius:

`0.50 / sqrt(round)`

Before the exponentiated update, seat gaps are centered by their current dual-weighted mean and normalized by the largest absolute centered gap. Therefore the maximum absolute log-weight movement is bounded by the dual radius. The seat weights are then normalized back to the simplex.

Initial dual weights are uniform `(1/N, ..., 1/N)`.

No dual floor, seat-specific hand tuning or texture-specific parameter is allowed.

## Frozen final gate

After round 32, run the original independent response validator once:

- BR learn samples: 250,000;
- holdout samples: 250,000;
- coverage must equal 100%;
- **every seat** unilateral-gain 95% upper bound must be <= **0.030000 ante**.

The threshold is unchanged from P4C/P4D/P4E.

## Decision rule

- If **both** frozen N=3 cases PASS, predeclare one N=4..8 P4F scaling schedule before any N=4 result and run the already-defined rainbow/monotone representatives once.
- If either N=3 case FAILS, P4F is BLOCKED. Do not add P4F rounds, alter primal/dual radii, change its warm-start checkpoint, increase samples, or relax the gate. Change solver method again.

No early stopping, parameter sweep, checkpoint selection or result-driven tuning is permitted.
