# P6 fail-soft recovery — validation/build result — 2026-09-09

## Status

**IMPLEMENTED ON FEATURE BRANCH; NOT YET MERGED/LIVE.**

DeepPot branch:

- `runtime/fail-soft-recovery-v1`
- draft PR: `pmartins87/DeepPot#1`

OpenHoldem integration branch:

- repository: `pmartins87/myoh_private`
- branch: `deeppot_failsoft_recovery_v1`
- stable predecessor preserved: `deeppot_runtime_v1`

## Runtime objective

The runtime must execute the immutable DeepPot strategy while remaining tolerant
to ordinary live scrape/state failures. Public-state recognition failure must
trigger repair/recovery rather than automatically becoming code 0/FOLD.

The recovery ladder is:

1. exact coherent state;
2. same-hand exact card/public-state memory;
3. frozen hand anchor for N, dealt mask, hero chair and BTN;
4. deterministic interpretation of unambiguous prior actions;
5. nearest legal public-state search for ambiguous/noisy evidence;
6. immutable-policy lookup over candidate states and weighted consensus;
7. nearest-policy tie-break when consensus is unresolved;
8. emergency TP+ STAY floor only after policy-backed public-state recovery is
   exhausted while exact/cached cards remain known.

The strategy bitsets are never retrained or altered by this layer.

## Fail-soft v3 action-history continuity

Adapter generation:

`failsoft-v3-action-history-20260909`

v3 retains the v2 frozen same-hand geometry and noisy-handreset tolerance and
adds protection against transient prior-action corruption.

A prior actor that disappears from both `playersplayingbits` and `foldbits2`
can legitimately be a missing-foldbit case, but it can also be a one-frame
`playersplayingbits` dropout of a real STAY. Therefore missing action evidence is
no longer accepted by the primary path as exact history. It is deferred to the
policy-backed recovery layer. If recent same-hand history showed the seat still
playing, both FOLD and STAY interpretations remain nearby candidates and the
immutable DeepPot policy participates in resolving the ambiguity.

Clear current evidence remains authoritative: playing-only is STAY and
folded-only is FOLD. A simultaneous playing+folded contradiction branches rather
than hard-failing.

## Hand continuity and cards

Once a coherent same-hand anchor exists, joins/leaves or a transient BTN/dealt
scrape cannot silently redefine N/action order for that hand. A hand-reset
callback is evidence, not an unconditional memory wipe; the boundary is confirmed
from lifecycle/card evidence before same-hand state is discarded.

Exact flop/hole cards are never approximated to different cards. A missing card
read may reuse only the valid exact identity cached for the same hand.

## `log_pf2` mandatory regressions

All six old `MISS state: ambiguous prior FOLD/STAY scrape` observations map to
legal public states:

| hand | N | actor | prior STAY mask | dense scenario | global code |
|---|---:|---:|---:|---:|---:|
| 7d5d / 9s4cAs | 7 | 4 | 5 | 20 | 135 |
| Qh4d / 3d7cTc | 8 | 6 | 20 | 83 | 324 |
| Ah8d / 8h4dJs | 8 | 4 | 0 | 15 | 256 |
| Th5c / Qs2s8s | 8 | 7 | 33 | 159 | 400 |
| Tc7s / 7d6h4d | 8 | 5 | 0 | 31 | 272 |
| Ts9s / Th3sAd | 8 | 4 | 4 | 19 | 260 |

The historical Tc7s hand is not a rollout gate. The correction is prospective.

## Fault-injection coverage

The branch now also exercises:

- exact round-trip of all **494** legal public decision states;
- missing `foldbits2` across the legal catalogue;
- one-frame prior-STAY `playersplayingbits` dropout with same-hand history;
- missing BTN/history recovery;
- mid-hand extra-seat/dealt-mask contamination;
- combined BTN + seat-mask noise;
- playing+folded contradictions;
- portable C++ parity for the transient action-history dropout.

Latest DeepPot CI:

- run: `34314311875`
- head: `8584d74c3a6bc48a84e6ee112d9cb89cfad90c75`
- result: **PASS**

## Windows OpenHoldem build — v3

GitHub Actions run:

- repository: `pmartins87/myoh_private`
- branch: `deeppot_failsoft_recovery_v1`
- run: `34314447599`
- source commit: `c76c16e3c7904da5146fe1cdfb93dc8437411551`
- configuration: `Release | Win32`
- result: **PASS**
- compiler/linker errors: **0**

Produced `user.dll` SHA256:

`A6E5DA3ED7239442A1C5EAC611C4C6C9A402B34BADE9A3382CA32CC804BA5B06`

Artifact:

- name: `deeppot-userdll-win32`
- artifact ID: `10089555181`
- artifact ZIP SHA256: `e1bbddd38a8cb162c4f4edf3a5b18a56a546a50a5943e1f0c469e65542226e3a`

The build emitted only the existing non-blocking OpenHoldem/project-name warnings
and zero compile/link errors.

## Action transport

Codes `1..494` remain the immutable trained scenario/action codes. Code `495`
is reserved outside the trained catalogue as `EMERGENCY_STAY_CODE`.

The matching fail-soft operational formula supports `495`, does not preempt the
DLL with `f$ScrapeError`, and uses the established STAY transport `BetMax`.

## Next gate

The next gate is a short controlled live test using the v3 DLL and matching
formula. Inspect only DeepPot runtime lines relevant to the strategy pipeline:

- `adapter loaded version=failsoft-v3-action-history-20260909`;
- `HIT EXACT`;
- `HIT RECOVERED_PRIMARY`;
- `HIT RECOVERED_CONSENSUS` / `HIT RECOVERED_NEAREST_TIEBREAK`;
- `EMERGENCY`;
- `MISS UNRECOVERABLE`.

Only after a clean live gate should the feature branch be promoted/merged.
