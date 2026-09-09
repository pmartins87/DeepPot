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

## What changed

The runtime no longer treats ordinary public-state scrape inconsistency as an
automatic reason to return zero/FOLD.

The recovery architecture is now:

1. exact/coherent state;
2. deterministic repair for known live semantics such as incomplete `foldbits2`;
3. same-hand memory (BTN/table geometry/cards/snapshots);
4. nearest legal public-state search;
5. immutable-policy lookup for candidate states and weighted action consensus;
6. nearest-policy tie-break if the accepted nearest candidates disagree;
7. emergency TP+ STAY floor only when public-state reconstruction itself remains
   impossible while exact/cached flop+hole cards are known.

Card identity is never approximated to a different card state. A transient card
read may reuse only a valid same-hand cached observation.

## `log_pf2` mandatory regressions

All six old `MISS state: ambiguous prior FOLD/STAY scrape` observations now map
to legal public states in the portable recovery reference and C++ regression
harness:

| hand | N | actor | prior STAY mask | dense scenario | global code |
|---|---:|---:|---:|---:|---:|
| 7d5d / 9s4cAs | 7 | 4 | 5 | 20 | 135 |
| Qh4d / 3d7cTc | 8 | 6 | 20 | 83 | 324 |
| Ah8d / 8h4dJs | 8 | 4 | 0 | 15 | 256 |
| Th5c / Qs2s8s | 8 | 7 | 33 | 159 | 400 |
| Tc7s / 7d6h4d | 8 | 5 | 0 | 31 | 272 |
| Ts9s / Th3sAd | 8 | 4 | 4 | 19 | 260 |

The Tc7s hand therefore no longer dies at state reconstruction. Its correct
runtime question is the immutable policy lookup for `N=8`, `actor=5`,
`prior_stay_mask=0`, exact flop `7d 6h 4d`, exact hole `Tc 7s`.

Historical replay outcomes are diagnostic evidence, not a rollout gate. By user
decision on 2026-09-09, the already-passed Tc7s hand will not be re-queried or
replayed as a prerequisite. The required correction is prospective: future
instances of this failure class must reach a legal policy lookup instead of
code 0/FOLD.

## Portable CI

The Python reference and portable C++ recovery harness pass the DeepPot GitHub
CI. The C++ harness compiles `deeppot_runtime_core.cpp` plus
`deeppot_live_recovery.cpp` and checks the six `log_pf2` regressions, missing-BTN
history recovery, playing+folded branching and the TP+ emergency classifier.

## Windows OpenHoldem build

GitHub Actions run:

- repository: `pmartins87/myoh_private`
- branch: `deeppot_failsoft_recovery_v1`
- run: `34311113443`
- runner: Windows Server 2022 / Visual Studio 2022 Enterprise
- MSVC: `14.44.35207`
- configuration: `Release | Win32`
- result: **PASS**
- compiler/linker errors: **0**

Built sources include:

- `deeppot_runtime_core.cpp`
- `deeppot_live_recovery.cpp`
- `OpenHoldemFunctions.cpp`
- `deeppot_userdll_failsoft.cpp`

Produced `user.dll` SHA256:

`0B8111C052EBEE619AF7DD5B5D9FA55B76E5CDC56D57D27232EFED3F182CDB47`

Artifact:

- name: `deeppot-userdll-win32`
- artifact ID: `10088399212`
- artifact ZIP SHA256: `2f743b2b1fe3b74a84dd086133a210e364371bac4ac135f0ddc1dd3530de6d73`

The three build warnings are the same non-blocking legacy/project-name warnings
already present in the previous DeepPot user-DLL build: one OpenHoldem C4229 and
two MSB8012 output-name warnings. There were no new compile/link errors.

## Formula transport change

Codes `1..494` remain the immutable trained scenario/action codes.

`495` is reserved outside the trained catalogue as `EMERGENCY_STAY_CODE`. It is
used only by the final TP+ operational floor when no public-state candidate can
be reconstructed. The generated OpenPPL formula routes `495` directly to the
configured STAY action.

The validated live STAY transport is `BetMax`, matching the current operational
DeepPot semantics. `BetPot` is no longer the default/packaging token for this
runtime branch.

The flop router no longer preempts the DLL with `f$ScrapeError`; otherwise a bad
`nplayersdealt` scrape would force FOLD before the DLL got the chance to repair
that exact problem.

## Rollout checklist

1. Produce the matching operational formula with code `495` support and `BetMax`
   as STAY transport.
2. Install the already-built fail-soft `user.dll` together with that formula in
   a controlled i5 test setup.
3. Run a short controlled live test and inspect the resulting log for
   `HIT EXACT`, `HIT RECOVERED*`, `EMERGENCY`, and `MISS UNRECOVERABLE` events.
4. Only after that merge/promote the feature branches.

The objective is prospective: prevent the same class of scrape/runtime failure
from creating avoidable FOLDs in future decisions, without retraining or changing
the immutable strategy bitsets.
