from __future__ import annotations

import argparse
from pathlib import Path

SHADOW_FORMULA_VERSION = "2026-09-08.p8-shadow.1"


def generate_shadow_formula(*, runtime_manifest_sha256: str) -> str:
    """Generate a no-action OpenHoldem shadow formula.

    The file intentionally contains no Fold/Call/Bet/Raise/Allin action tokens.
    The only DeepPot query lives in f$debug so the operator can press Auto in
    OpenHoldem's debug tab and force one evaluation per heartbeat while the
    Autoplayer remains OFF. The user.dll itself logs HIT/MISS and the encoded
    recommendation when dll$deeppot_action is evaluated.
    """

    lines = [
        "##notes##",
        "// ============================================================================",
        "// DEEPPOT SHADOW SAFE — NO ACTION COMMANDS",
        "// ============================================================================",
        f"// Shadow formula version: {SHADOW_FORMULA_VERSION}",
        f"// Runtime manifest SHA256: {runtime_manifest_sha256}",
        "// PURPOSE: live scraping/state validation only.",
        "// This file contains NO Fold/Call/Bet/Raise/Allin action command.",
        "// Keep OpenHoldem Autoplayer OFF.",
        "// Open Formula Editor -> Debug and press Auto to evaluate once per heartbeat.",
        "// dll$deeppot_action returns 0 on MISS, +scenario for STAY, -scenario for FOLD.",
        "// user.dll writes [DeepPot] HIT/MISS records to the OpenHoldem log.",
        "// ============================================================================",
        "",
        "##f$preflop##",
        "",
        "##f$flop##",
        "",
        "##f$turn##",
        "",
        "##f$river##",
        "",
        "##f$debug##",
        "= dll$deeppot_action",
        "= ismyturn",
        "= betround",
        "= ncommoncardsknown",
        "= nchairs",
        "= dealerchair",
        "= userchair",
        "= nplayersdealt",
        "= playersdealtbits",
        "= playersplayingbits",
        "= foldbits2",
        "= $$pr0",
        "= $$ps0",
        "= $$pr1",
        "= $$ps1",
        "= $$cr0",
        "= $$cs0",
        "= $$cr1",
        "= $$cs1",
        "= $$cr2",
        "= $$cs2",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate DeepPot no-action OpenHoldem shadow formula")
    ap.add_argument("--out", required=True)
    ap.add_argument("--runtime-manifest-sha256", required=True)
    args = ap.parse_args()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        generate_shadow_formula(runtime_manifest_sha256=args.runtime_manifest_sha256),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
