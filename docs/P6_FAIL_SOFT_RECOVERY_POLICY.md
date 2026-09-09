# P6 — Fail-soft live-state recovery policy

Date: 2026-09-09

## Purpose

DeepPot must not turn an ordinary scrape inconsistency into an automatic FOLD.
The mathematical policy remains immutable; the runtime adapter is responsible for
mapping noisy live observations to the closest legal public state that the policy
already knows.

The runtime policy is therefore **fail-soft**, not fail-closed, for recoverable
live-state errors.

## Non-negotiable rules

1. Prefer an exact state when the scrape is coherent.
2. If the current scrape is inconsistent, repair it from redundant symbols and
   same-hand history before giving up.
3. If more than one repaired state is plausible, query the trained policy for
   the closest legal candidates and resolve by weighted consensus.
4. A recoverable public-state error must not return `dll$deeppot_action = 0`.
5. `0` is reserved for genuinely unrecoverable failures such as runtime package
   load failure or absence of any trustworthy/cached hero+flop card identity.
6. Never approximate the hero cards or flop to *different* cards. Card identity
   may be recovered only from a valid same-hand cached observation. Nearest-state
   search applies to the **public table state**, not to card strength.
7. Every repair must be logged as `RECOVERED` with reason, distance/cost and the
   candidate/consensus used. Emergency heuristics must be logged as `EMERGENCY`.

## Evidence hierarchy

For the one-decision Pot Fold street, use evidence in this order:

- same-hand stable snapshot history;
- current `playersplayingbits`;
- current `playersdealtbits` and `nplayersdealt`;
- current/last-valid BTN (`dealerchair`);
- current `foldbits2` as corroborating evidence, not as a mandatory fold record.

`foldbits2` is known not to retain every prior fold after the cardback disappears.
A prior actor that has already acted and is no longer present in
`playersplayingbits` is therefore normally inferred as FOLD.

A player simultaneously present in `playersplayingbits` and `foldbits2` is a
contradiction to be repaired/branched, not an immediate hard MISS.

## Same-hand memory

The user DLL should use the OpenHoldem lifecycle callbacks instead of treating a
single action-time scrape as the whole truth.

Persist, at minimum:

- last valid `dealerchair`;
- stable dealt mask / dealt count;
- latest playing/folded masks;
- hero chair;
- last valid hero hole cards;
- last valid three-card flop;
- a small rolling set of recent coherent snapshots.

Reset hand memory on `DLLUpdateOnHandreset()`.
Refresh observations on heartbeat/new-round/my-turn callbacks when symbols are
valid. A player entering or leaving the visible table mid-hand must not silently
rewrite the stable dealt set for the hand.

## Public-state recovery

### Tier 0 — EXACT

Current scrape directly reconstructs a legal `(N, actor, prior_stay_mask)` and
exact card key. Query the immutable bitset and return the signed scenario code.

### Tier 1 — REPAIRED

Repair only missing/inconsistent observations while preserving all strong
current evidence. Examples:

- missing `foldbits2` -> infer prior FOLD from absence in `playersplayingbits`;
- transient BTN loss -> use last valid same-hand BTN;
- current dealt mask differs from stable same-hand dealt mask -> prefer stable
  hand mask when the change is consistent with a seat joining/leaving the table;
- `nplayersdealt` disagrees with a mask by one seat -> score both interpretations;
- playing+folded contradiction -> branch the actor state and let the candidate
  scorer/strategy consensus resolve it.

### Tier 2 — NEAREST LEGAL STATE

If no single repaired state is uniquely supported, generate legal candidate
public states and assign an evidence cost. Lower cost means closer to the live
observation.

Suggested cost ordering (the exact constants are implementation details and must
be deterministic/tested):

- fill an absent prior fold from `playersplayingbits`: very low cost;
- use last valid same-hand BTN/dealt mask: low cost;
- change one uncertain prior FOLD/STAY bit: low/moderate cost;
- add/remove one uncertain dealt seat: moderate cost;
- use a BTN with no current/history support: higher cost;
- contradict a clear current playing/dealt observation: very high cost.

Do not stop at the first syntactically legal candidate. Query the trained policy
for the closest candidate set.

## Candidate action consensus

For candidates inside the accepted nearest-cost window:

- query the exact immutable DeepPot strategy for the same hero cards/flop;
- weight each action by candidate proximity;
- if the weighted result has a clear winner, execute that action;
- log candidate count, minimum cost and STAY/FOLD weights.

This keeps recovery strategy-driven instead of replacing the solver with a hand
heuristic.

## Emergency floor

If public-state reconstruction remains too ambiguous but exact/cached cards are
valid, perform a broader policy consensus over legal nearby public states before
using any heuristic.

If even that is inconclusive, **TP+ on the flop must never be auto-folded solely
because state reconstruction failed**. In that final emergency condition use
STAY and log `EMERGENCY TP_PLUS -> STAY`.

This TP+ floor is not a replacement strategy. It is a last-resort operational
safety rule that applies only after exact/repaired/nearest policy lookup failed.

For weaker hands, a deterministic conservative emergency rule may still return
FOLD when no policy-backed resolution is possible.

## Logging contract

Examples:

```text
[DeepPot] HIT EXACT N=8 actor=5 scenario=31 code=272 ... action=STAY
[DeepPot] HIT RECOVERED cost=1 reason=infer_missing_foldbits N=8 actor=5 scenario=31 code=272 ... action=STAY
[DeepPot] HIT RECOVERED_CONSENSUS candidates=6 min_cost=2 stay_weight=0.91 fold_weight=0.09 code=... action=STAY
[DeepPot] EMERGENCY TP_PLUS -> STAY reason=public_state_unresolved
[DeepPot] MISS UNRECOVERABLE reason=cards_unavailable_no_same_hand_cache
```

A runtime test log should contain no generic `MISS state -> 0 -> FOLD` for a
recoverable public-state inconsistency.

## `log_pf2` regression cases

The six `ambiguous prior FOLD/STAY scrape` decisions from `log_pf2` are mandatory
regressions. With the corrected primary interpretation of `playersplayingbits`,
all six already map to legal public states rather than `0`:

| hand | recovered N | actor | prior STAY mask | dense scenario | global code |
|---|---:|---:|---:|---:|---:|
| 7d5d / 9s4cAs | 7 | 4 | 5 | 20 | 135 |
| Qh4d / 3d7cTc | 8 | 6 | 20 | 83 | 324 |
| Ah8d / 8h4dJs | 8 | 4 | 0 | 15 | 256 |
| Th5c / Qs2s8s | 8 | 7 | 33 | 159 | 400 |
| Tc7s / 7d6h4d | 8 | 5 | 0 | 31 | 272 |
| Ts9s / Th3sAd | 8 | 4 | 4 | 19 | 260 |

The Tc7s hand is the canonical regression: a technical state miss must not be
silently converted to FOLD. The runtime must first recover scenario 31/global
code 272 and then let the immutable strategy decide STAY/FOLD for the exact
Tc7s / 7d6h4d card state.

## Acceptance gate

Before replacing the current live DLL:

1. all existing exact runtime equivalence tests remain PASS;
2. the six `log_pf2` MISS states recover to the table above;
3. synthetic tests cover BTN loss, one-seat dealt mismatch, seat join/leave,
   playing+folded contradiction and temporary card disappearance with same-hand
   cache;
4. exact coherent states produce exactly the same action as the old runtime;
5. no recoverable public-state test returns zero;
6. Windows Release|Win32 user.dll builds successfully;
7. only then perform a short controlled i5 live test.
