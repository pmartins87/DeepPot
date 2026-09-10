# P6 fail-soft v3 live failure — 2026-09-09

## Verdict

**FAIL — do not deploy/promote `failsoft-v3-action-history-20260909`.**

The first controlled live run exposed a structural recovery bug in the frozen-hand anchor. The immutable DeepPot strategy bitsets are not implicated. The adapter supplied the strategy with the wrong public player-count/action-order state after freezing an early, internally consistent but incomplete scrape.

## Root cause

v3 promoted the **first internally coherent** `playersdealtbits / nplayersdealt / dealer / hero` observation to a hard hand anchor. `ApplyHandAnchor()` then overwrote later live `playersdealtbits` and `nplayersdealt` with that frozen geometry.

An internally consistent snapshot is not necessarily complete. During table/hand transitions the scraper can temporarily expose only part of the dealt field while `bitcount(playersdealtbits) == nplayersdealt` still holds. v3 mistook those partial snapshots for authoritative hand geometry.

The live regression shows that this can silently query the correct immutable strategy with the **wrong N and wrong actor/history**, producing a strategically unrelated BET/FOLD decision.

## Mandatory live regressions from `oh_0` (2026-09-09)

### Qc2c / Tc6h9d

Early anchor:

- dealer=1, hero=2
- dealt=`0x7`
- N=3

Decision-time raw scrape:

- dealer=1, hero=2
- playersdealtbits=223 (`0xDF`)
- nplayersdealt=7
- playersplayingbits=223

v3 output:

- `HIT RECOVERED_PRIMARY`
- forced `dealt_from_hand_anchor,nplayersdealt_from_hand_anchor`
- queried **N=3 actor=0 scenario=0 code=3**
- action=STAY/BET

This is invalid recovery. The current decision snapshot itself was coherent N=7 and must not have been overwritten by the stale partial anchor.

### 9s5s / 2c8hAh

Early anchor:

- dealer=3, hero=2
- dealt=`0xF`
- N=4

Decision-time raw scrape:

- playersdealtbits=223 (`0xDF`)
- nplayersdealt=7
- playersplayingbits=30
- foldbits2=193

v3 forced N=4 and returned FOLD. The output happened to be FOLD, but the lookup state was still wrong and therefore cannot be accepted as strategically valid.

### Js5d / 7sQc8d

Early anchor:

- dealer=4, hero=2
- dealt=`0x3F`
- N=6

Decision-time raw scrape:

- playersdealtbits=255 (`0xFF`)
- nplayersdealt=8
- playersplayingbits=156
- foldbits2=67

v3 recovered/query-selected **N=6 actor=3 scenario=7 code=60**, action=STAY/BET, even though the coherent live public geometry was N=8.

Again, this is an adapter state-reconstruction failure, not evidence that the trained DeepPot policy intentionally jams Js5d in the true N=8 state.

## Required v4 correction

1. **A coherent decision-time snapshot has priority over an older anchor.** A hand anchor is fallback evidence, never unconditional truth.
2. **Reject/bypass an anchor contradicted by action evidence.** If `(playersplayingbits | foldbits2)` contains any seat absent from `anchor.playersdealtbits`, the anchor is provably incomplete for this hand and must not overwrite current geometry.
3. **Do not poison history with forced anchor geometry.** Preserve raw coherent same-hand observations; use anchor only as a candidate/fallback during recovery.
4. Keep exact cards immutable/cached as already implemented.
5. Keep the trained strategy immutable. The fix is only in state reconstruction.
6. Add the three live cases above as mandatory regression tests before another Windows build/live rollout.
7. Live acceptance requires no decision where the adapter's chosen N contradicts a coherent decision-time `playersdealtbits/nplayersdealt` snapshot without explicit, stronger same-hand evidence explaining the override.

## v4 patch status

A focused source correction has now been applied on the feature branch as adapter generation `failsoft-v4-anchor-evidence-20260909`. `ApplyHandAnchor()` rejects the frozen anchor when current `playersplayingbits | foldbits2` proves that a seat omitted by the anchor actually participated in the hand. A source regression contract requires this guard before CI can pass.

This is intentionally still **not approved for live use** until the full CI + Windows Release|Win32 build and the new exact live regressions pass.

## Immediate operational status

v3 is withdrawn from live use. Restore the pre-v3 `user.dll`/formula backup or keep OpenHoldem stopped until a v4 build passes the new regressions.
