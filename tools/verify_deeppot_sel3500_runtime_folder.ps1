param(
    [string]$RuntimeDir = ".\DeepPotRuntime"
)

$ErrorActionPreference = "Stop"

$ReleaseName = "V2_SEL3500 greedy"
$Expected = [ordered]@{
    "deeppot_runtime_manifest.json" = "717c2fd0582e91d293b92fea1fc7355524681976a6856b8c5b6e70e2b3e01158"
    "deeppot_runtime_index.bin"      = "fb8bff8f21efd253ec6374de920de74d9fa662df673d5cd579f68fad152b6f74"
    "strategy\N2_final.bits"        = "0c79464c9475bfd698db862802d47a39e42154daa22237566232d594614f0b85"
    "strategy\N3_final.bits"        = "aedf07cbe3437abb5cb92ed43f2bc675ae618f6f12ec68c9b665e7e1013cb09f"
    "strategy\N4_final.bits"        = "39adb5bc6c9ddf40cff1da340e197319553f8d4e2e7f03baff18829ed57cdd1a"
    "strategy\N5_final.bits"        = "ea5e99f3202ee9ce0449cc4fb81c9ea175fbe19589707fb9a7cd06b3ca3892a7"
    "strategy\N6_final.bits"        = "7f01583f8798d0c8bffd8055ba289aac00427efc241167ccd8dd9c9bd35d65d6"
    "strategy\N7_final.bits"        = "616355968e9eebeaf8603eac47c15c4150f3cdfab2db9df4f36fef558ecd364b"
    "strategy\N8_final.bits"        = "2603653db79381d92df02a132743ece3f6bfe5da0408536427101c5c722a5519"
}

$runtime = (Resolve-Path $RuntimeDir -ErrorAction Stop).Path
Write-Host "DeepPot SEL3500 frozen runtime verifier" -ForegroundColor Green
Write-Host "  release: $ReleaseName"
Write-Host "  runtime: $runtime"

foreach ($relative in $Expected.Keys) {
    $path = Join-Path $runtime $relative
    if (-not (Test-Path $path -PathType Leaf)) {
        throw "Required release file is missing: $path"
    }
    $actual = (Get-FileHash $path -Algorithm SHA256).Hash.ToLowerInvariant()
    $wanted = $Expected[$relative]
    if ($actual -ne $wanted) {
        throw "SHA256 mismatch for $relative`n  expected: $wanted`n  actual:   $actual"
    }
    Write-Host "  PASS $relative"
}

Write-Host ""
Write-Host "SEL3500 RUNTIME HASH VERIFICATION PASS." -ForegroundColor Green
Write-Host "  verified files: $($Expected.Count)"
Write-Host "  policy: V2_SEL3500 greedy"
Write-Host "  release-equivalence scope: 635,675,248 exact infosets, 0 action mismatches"
Write-Host ""
Write-Host "This verifies the frozen runtime files only. It does not verify live scraping/tablemap state." -ForegroundColor Yellow
