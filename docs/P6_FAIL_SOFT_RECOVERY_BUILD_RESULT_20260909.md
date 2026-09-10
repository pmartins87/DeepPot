# P6 fail-soft recovery — validation/build result — 2026-09-09

## Current status

**V3 FAILED THE FIRST CONTROLLED LIVE GATE — DO NOT DEPLOY/PROMOTE.**

DeepPot branch:

- `runtime/fail-soft-recovery-v1`
- draft PR: `pmartins87/DeepPot#1`

OpenHoldem integration branch:

- repository: `pmartins87/myoh_private`
- branch: `deeppot_failsoft_recovery_v1`
- stable predecessor preserved: `deeppot_runtime_v1`

The immutable trained DeepPot strategy remains unchanged. The live failure is in the runtime state-reconstruction adapter.

## Live v3 failure

Controlled live log `oh_0` on 2026-09-09 showed that `failsoft-v3-action-history-20260909` can freeze an early, internally consistent but incomplete dealt-player mask and then overwrite a later coherent decision-time state with that stale anchor.

Observed mandatory regressions:

| hand | early frozen anchor | coherent decision-time state | v3 queried state | result |
|---|---|---|---|---|
| Qc2c / Tc6h9d | N=3, dealt=0x7 | N=7, dealt=0xDF | N=3 actor=0 code=3 | STAY/BET — invalid state selection |
| 9s5s / 2c8hAh | N=4, dealt=0xF | N=7, dealt=0xDF | N=4 actor=2 code=-14 | FOLD — action coincidental; state selection invalid |
| Js5d / 7sQc8d | N=6, dealt=0x3F | N=8, dealt=0xFF | N=6 actor=3 code=60 | STAY/BET — invalid state selection |

The root cause and required v4 correction are frozen in `docs/P6_FAIL_SOFT_V3_LIVE_FAILURE_20260909.md`.

## Required v4 gate

Before another live deployment:

1. coherent decision-time public geometry must outrank an older anchor;
2. an anchor must be rejected/bypassed when current playing/fold evidence contains a seat absent from the anchor dealt mask;
3. same-hand history must preserve raw coherent geometry rather than forced/anchored copies;
4. exact-card cache remains same-hand only;
5. the three live v3 failures become mandatory regressions;
6. all prior six `log_pf2` recovery regressions remain mandatory;
7. full Python/C++ CI and Windows Release|Win32 build must pass.

## Operational instruction

Do not use the v3 DLL/formula for further live play. Restore the pre-v3 backup or keep OpenHoldem stopped until v4 passes the new regression gate.
