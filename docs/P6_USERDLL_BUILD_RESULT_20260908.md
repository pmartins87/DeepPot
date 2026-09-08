# P6 OpenHoldem user.dll build result — 2026-09-08

## Result

**PASS** — the dedicated DeepPot OpenHoldem user DLL compiles successfully as Release/Win32 with the existing OpenHoldem user-DLL interface.

Repository: `pmartins87/myoh_private`
Branch: `deeppot_runtime_v1`
Build commit: `9565df889073e3e11f1eac31583ec1614179e7a6`
GitHub Actions run: `34192014659`
Job: `101951834050`
Runner: Windows Server 2022 / Visual Studio 2022 Enterprise / MSVC 14.44.35207
Configuration: Release | Win32
Errors: 0

Produced file:

`user.dll`

DLL SHA256 reported by the build:

`0F939BAC4D5B3E95DCC219D0EC99CCB6FE4B12D97860FFAD5FA01A1E504C1FC9`

Artifact:

- name: `deeppot-userdll-win32`
- artifact ID: `10042546697`
- artifact ZIP digest: `sha256:716e2058b2b7ad162c57e2b61e9aa279a31163b44ce5c38a5c05d1e8b1a03219`

## Build-history note

The first attempt, run `34191909172`, used the then-current `windows-latest` image (Windows 2025 / VS2026) and failed because OpenHoldem's unchanged `OpenHoldemFunctions.cpp` includes `atlstr.h`, which was absent from that runner image.

No DeepPot code or OpenHoldem interface semantics were changed to work around it. The deterministic build gate was moved to the VS2022 runner, matching the project's v143-era build environment, and the next run compiled successfully.

## Relevant warnings

The successful build emitted one legacy `C4229` warning from OpenHoldem's existing `OpenHoldemFunctions.cpp` and MSBuild target-name/output-name warnings because the project display name is `DeepPot User DLL` while the linker output is intentionally `user.dll`. There were zero compiler/linker errors and the expected `user.dll` was produced and hashed.

These warnings do not alter the runtime logic. They may be cleaned later without changing the runtime contract, but they are not a release blocker.

## What this proves — and what it does not

This PASS proves that:

- the DeepPot adapter compiles against the actual OpenHoldem `user.h` / `OpenHoldemFunctions` interface;
- the exact C++ runtime core links into the Win32 user DLL;
- the output artifact is reproducible and hashable.

It does **not** yet prove live Pot Fold scraping or button semantics. The following remain live-dependent:

- tablemap/scraper correctness;
- chair orientation/action order;
- prior FOLD/STAY reconstruction from OpenHoldem symbols;
- the exact client action corresponding to Pot Fold STAY/POT.

Autoplayer remains disabled until those items pass shadow validation.
