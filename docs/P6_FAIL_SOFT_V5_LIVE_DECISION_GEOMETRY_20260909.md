# P6 fail-soft v5 — live decision geometry

Date: 2026-09-09

## Trigger

The first controlled v4 field log showed that v4 fixed stale partial N/dealt anchors, but an older anchor could still overwrite a complete decision-time `userchair` or `dealerchair` when no outside-seat contradiction existed.

Three exact v4 failures were retained as regressions:

- `5s5c / Th Kc 7c`: decision-time N8 / actor1 / scenario1, but stale Hero anchor produced actor4 / scenario29.
- `Qc7s / As 9d Jd`: decision-time N5 / actor1 / scenario2, but stale BTN anchor produced actor2 / scenario6.
- `Ad7d / Ks 3d 5h`: decision-time N5 / actor1 / scenario1, but stale BTN anchor produced actor2 / scenario4.

## v5 rule

A decision-time public snapshot outranks an older anchor only when all of the following hold:

- current exact flop + Hero hole cards are live rather than cache-recovered;
- `nchairs`, Hero chair, dealer chair and N/dealt are internally coherent;
- playing/fold masks are subsets of dealt;
- playing and fold masks do not overlap;
- playing OR fold exactly partitions all dealt seats;
- Hero is playing and not folded.

When this gate passes, v5 emits `live_decision_geometry_preferred_over_anchor` if the old anchor disagrees and preserves the current Hero/BTN/N/dealt geometry. If the gate does not pass, the same-hand anchor/history remains available for fail-soft repair. The v4 outside-seat anchor rejection remains as a secondary defense.

The immutable trained strategy package is unchanged.

## Separate strategy-quality observation

The same v4 field log also contained unusual STAY decisions that were *not* caused by the stale-anchor bug. Their decision-time public-state reconstruction is internally consistent:

- `KdTh / 7h Ac 4s`: N5 actor0 scenario0 -> STAY.
- `Ts9s / As Kc 9c`: N4 actor2 scenario5 -> STAY.
- `AcTc / 5d Jh 9c`: N4 actor3 scenario10 -> STAY.

These hands therefore belong to a separate immutable-policy/training-quality audit after runtime state reconstruction is live-safe. They must not be patched ad hoc in the runtime adapter.
