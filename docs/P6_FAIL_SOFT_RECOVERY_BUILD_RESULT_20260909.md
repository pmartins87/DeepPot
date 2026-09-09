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

The current recovery ladder is:

1. exact coherent state;
2. deterministic repair of known one-decision semantics such as incomplete
   `foldbits2`;
3. same-hand memory for cards and public state;
4. frozen same-hand public anchor for `N`, dealt mask, hero chair and BTN;
5. nearest legal public-state search;
6. immutable-policy lookup for candidate states and weighted consensus;
7. nearest-candidate policy tie-break if consensus is unresolved;
8. emergency TP+ STAY floor only when public-state reconstruction itself is
   impossible while exact/cached cards remain known.

The strategy bitsets are never retrained or altered by this layer.

## Fail-soft v2 hand continuity

Adapter generation:

`failsoft-v2-hand-anchor-20260909`

The v2 adapter adds two important protections that were missing from v1:

- **frozen hand geometry**: once a coherent hand snapshot exists, the current
  hand keeps its original dealt mask/N and BTN even if a player joins, leaves,
  disappears from the scrape, or the BTN later becomes unreadable;
- **no blind memory wipe on `DLLUpdateOnHandreset()`**: a hand-reset callback is
  treated as evidence and confirmed by a non-flop transition or changed exact
  card identity before same-hand memory is discarded. This prevents a noisy
  lifecycle callback from destroying precisely the history needed for recovery.

History supplied to nearest-state recovery is structurally anchored while live
playing/fold evidence remains current.

The DLL also writes its adapter generation to the log at load time so a stale
binary can be identified directly from the live log.

## Card handling

Exact flop/hole cards are never approximated to different cards. A missing card
read can reuse only the valid exact card identity already cached for the same
hand. Structural recovery changes public state only; it does not map one poker
hand to another.

## `log_pf2` mandatory regressions

All six old `MISS state: ambiguous prior FOLD/STAY scrape` observations map to
legal public states in the portable recovery regression suite:

| hand | N | actor | prior STAY mask | dense scenario | global code |
|---|---:|---:|---:|---:|---:|
| 7d5d / 9s4cAs | 7 | 4 | 5 | 20 | 135 |
| Qh4d / 3d7cTc | 8 | 6 | 20 | 83 | 324 |
| Ah8d / 8h4dJs | 8 | 4 | 0 | 15 | 256 |
| Th5c / Qs2s8s | 8 | 7 | 33 | 159 | 400 |
| Tc7s / 7d6h4d | 8 | 5 | 0 | 31 | 272 |
| Ts9s / Th3sAd | 8 | 4 | 4 | 19 | 260 |

The historical Tc7s hand is not a rollout gate. The correction is prospective:
future occurrences of this failure class must reach the trained policy instead
of dying at public-state reconstruction.

## DeepPot CI

Current head validation:

- GitHub Actions run: `34313441110`
- result: **PASS**
- includes Python recovery tests, portable C++ recovery tests, all six `log_pf2`
  regressions, BTN-loss/history recovery, seat-mask inconsistency,
  playing+folded contradiction, emergency TP+ classification, and source-contract
  checks that handreset no longer blindly wipes same-hand memory and the hand
  anchor is applied before primary lookup.

## Windows OpenHoldem build — v2

GitHub Actions run:

- repository: `pmartins87/myoh_private`
- branch: `deeppot_failsoft_recovery_v1`
- run: `34313248737`
- source commit: `fecb7173c4adc6744cd4e9d2941ce885d600c4bc`
- runner: Windows Server 2022 / Visual Studio 2022 Enterprise
- MSVC: `14.44.35207`
- configuration: `Release | Win32`
- result: **PASS**
- compiler/linker errors: **0**

Produced `user.dll` SHA256:

`70440DCB0DBAF9D3563F5065D15D1481F01C524E6550205929917D89F8132ACE`

Artifact:

- name: `deeppot-userdll-win32`
- artifact ID: `10089143070`
- artifact ZIP SHA256: `c19b1dca22b4685372d40bfd0e2caf8bc4b95e7cd126de7589f37b7144a73242`

The build emitted only the same three non-blocking legacy/project-name warnings
seen previously: one OpenHoldem C4229 and two MSB8012 output-name warnings.
There were zero new compiler/linker errors.

## Action transport

Codes `1..494` remain the immutable trained scenario/action codes. Code `495`
is reserved outside the trained catalogue as `EMERGENCY_STAY_CODE`, used only by
the final TP+ operational floor when no legal public-state candidate survives.

The generated operational formula supports code `495`, does not preempt the DLL
with `f$ScrapeError`, and uses the already-established live STAY transport token
`BetMax`.

## Next gate

The code/build gate is complete. The remaining gate is a short controlled live
test using the v2 DLL and matching fail-soft formula, followed by inspection of
DeepPot-only runtime lines:

- `adapter loaded version=failsoft-v2-hand-anchor-20260909`;
- `HIT EXACT`;
- `HIT RECOVERED_PRIMARY`;
- `HIT RECOVERED_CONSENSUS` / `HIT RECOVERED_NEAREST_TIEBREAK`;
- `EMERGENCY`;
- `MISS UNRECOVERABLE`.

Only after that live gate should the feature branch be promoted/merged.
