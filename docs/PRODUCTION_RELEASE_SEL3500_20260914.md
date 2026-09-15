# DeepPot production release — V2_SEL3500 greedy

Date: 2026-09-14

## Release decision

The selected production base is **V2_SEL3500 greedy**.

Base-policy selection (D3) is closed and the dedicated mathematical-to-runtime production release gate (D4) has now passed.

This release does not authorize SEL4000, mixed/hybrid runtime work, or static BR-to-CFR overrides.

## D4 exhaustive release-equivalence result

Command:

```powershell
cd C:\DeepPot
git pull
powershell -ExecutionPolicy Bypass -File .\tools\verify_deeppot_sel3500_release.ps1
```

Result: **PASS**.

Global accounting:

- exact infosets: **635,675,248**;
- structurally resolvable infosets: **635,675,248**;
- action bit mismatches: **0**;
- index metadata mismatches: **0**;
- unknown supported keys: **0**;
- training stage: `completed`;
- snapshot: `V2_SEL3500`;
- live adapter contract: `failsoft-v5-live-decision-geometry-20260909`;
- `ready_for_live_v5`: `true`.

Frozen release hashes:

- snapshot manifest SHA256: `8c85b90f0493f7fb2913d41059d5d8ba86e1f8fb62e7e53d875adb7909d4c563`;
- runtime manifest SHA256: `717c2fd0582e91d293b92fea1fc7355524681976a6856b8c5b6e70e2b3e01158`;
- runtime index SHA256: `fb8bff8f21efd253ec6374de920de74d9fa662df673d5cd579f68fad152b6f74`;
- generated snapshot live formula SHA256: `935ae14673fb332f9fcb10f0889ed97a700846a393c55b44608b517e440eb6bc`.

Per-N runtime bitset SHA256:

- N2: `0c79464c9475bfd698db862802d47a39e42154daa22237566232d594614f0b85`;
- N3: `aedf07cbe3437abb5cb92ed43f2bc675ae618f6f12ec68c9b665e7e1013cb09f`;
- N4: `39adb5bc6c9ddf40cff1da340e197319553f8d4e2e7f03baff18829ed57cdd1a`;
- N5: `ea5e99f3202ee9ce0449cc4fb81c9ea175fbe19589707fb9a7cd06b3ca3892a7`;
- N6: `7f01583f8798d0c8bffd8055ba289aac00427efc241167ccd8dd9c9bd35d65d6`;
- N7: `616355968e9eebeaf8603eac47c15c4150f3cdfab2db9df4f36fef558ecd364b`;
- N8: `2603653db79381d92df02a132743ece3f6bfe5da0408536427101c5c722a5519`.

## What D4 proves

D4 verifies that every continuous-task greedy bitset used by the immutable SEL3500 snapshot is SHA-verified and compared byte-for-byte against the release runtime; all 1,755 canonical flop slots per N are checked against the runtime index card codes and hole-state widths; and all 635,675,248 exact infosets are accounted for.

Therefore the release runtime is an exact deterministic projection of the selected SEL3500 greedy mathematical policy, with no action/index loss introduced by packaging.

D4 does **not** prove live scraping correctness. Scraping/tablemap/action transport remains the final operational gate.

## Deployment policy

The i5 has an already-known-good live path (`DeepPot.txt`, `user.dll`, tablemap/live adapter). The SEL3500 release changes only strategy data.

Therefore the first deployment must be **runtime-only**:

- keep the current known-good `DeepPot.txt`;
- keep the current `user.dll`;
- keep the current tablemap;
- replace only the complete `DeepPotRuntime` folder after backing up the previous folder;
- verify the transferred runtime hashes before live use.

The snapshot-generated `DeepPot.txt` is not part of the first production deployment even though D4 recorded its SHA.

## Runtime-only packaging

Use:

```powershell
cd C:\DeepPot
git pull
powershell -ExecutionPolicy Bypass -File .\tools\prepare_deeppot_sel3500_deployment.ps1
```

The script refuses to package unless the D4 JSON is PASS and matches the frozen SEL3500 runtime manifest/index hashes. It emits a runtime-only ZIP under:

`C:\DeepPot\runs\production_release_SEL3500\DeepPot_SEL3500_RUNTIME_ONLY.zip`

The package includes a frozen hash verifier for use after transfer to the i5.

## Final operational gate

After the runtime-only package is transferred and hash-verified on the i5:

1. close OpenHoldem;
2. back up the currently working `DeepPotRuntime` folder;
3. replace only that folder with the frozen SEL3500 folder;
4. reopen OpenHoldem with the existing known-good formula/user.dll/tablemap;
5. run a finite live smoke validation of scraping and returned FOLD/STAY actions;
6. if the live adapter returns an invalid/zero action, wrong N/actor/history, or other scrape inconsistency, roll back the runtime folder and investigate before further play.

No additional CFR training is required for this release.
