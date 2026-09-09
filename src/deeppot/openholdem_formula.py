from __future__ import annotations

import argparse
from pathlib import Path

from .deepkk_style_export import enumerate_all_scenarios
from .runtime_contract import EMERGENCY_STAY_CODE, encoded_action_code


FORMULA_GENERATOR_VERSION = "2026-09-09.p6.failsoft2"


def generate_openholdem_formula(
    *,
    runtime_manifest_sha256: str = "PENDING",
    stay_action: str = "BetMax",
    live_enabled: bool = False,
) -> str:
    """Generate the DeepKK-like operational formula around one DLL query.

    The 494 situations and their STAY-membership functions are explicit in the
    text file. Actual exact list membership is answered by the runtime DLL from
    the immutable bitsets. Only ``dll$deeppot_action`` is queried because the
    OpenHoldem user-DLL symbol engine caches one ProcessQuery result per action
    orbit without distinguishing different dll$ symbol names.

    Codes 1..494 remain immutable trained scenario/action results. Code 495 is
    deliberately outside that catalogue and is only an emergency STAY transport
    sentinel used after fail-soft public-state recovery has been exhausted.

    Pot Fold live semantics are binary: STAY pays the maximum configured amount.
    The validated OpenPPL transport token is therefore BetMax, not BetPot.
    """

    if not stay_action or any(ch.isspace() for ch in stay_action):
        raise ValueError("stay_action must be one OpenPPL action token")

    specs = enumerate_all_scenarios()
    enabled_text = "true" if live_enabled else "false"
    lines: list[str] = [
        "##notes##",
        "// ============================================================================",
        "// DEEPPOT OPERACIONAL — DeepKK-style exact postflop lookup",
        "// ============================================================================",
        f"// Formula generator: {FORMULA_GENERATOR_VERSION}",
        f"// Runtime manifest SHA256: {runtime_manifest_sha256}",
        "// Mathematical base is immutable and remains separate from this formula.",
        "// 494 public scenarios are explicitly enumerated below.",
        "// Exact list membership lives in lossless runtime bitsets; no hand bucketting.",
        "// One DLL symbol only: dll$deeppot_action.",
        "// Return contract:",
        "//   0       = genuinely unrecoverable live state after fail-soft recovery",
        "//   +1..494 = STAY, magnitude identifies the global trained scenario",
        "//   -1..-494 = FOLD, magnitude identifies the global trained scenario",
        f"//   +{EMERGENCY_STAY_CODE}      = emergency STAY transport sentinel (not a trained scenario)",
        "//",
        f"// STAY execution token currently configured as: {stay_action}",
        "// IMPORTANT: fail-soft state recovery belongs in the DLL; this formula only",
        "// transports the already-resolved action. Zero remains the last unrecoverable",
        "// fallback, while the emergency STAY sentinel must execute STAY directly.",
        "// ============================================================================",
        "",
        "##f$deeppot_live_enabled##",
        f"{enabled_text}",
        "",
        "##f$ScrapeError##",
        "When nplayersdealt < 2 Return true Force",
        "When nplayersdealt > 8 Return true Force",
        "When betround = 2 && ncommoncardsknown != 3 Return true Force",
        "When Others Return false Force",
        "",
        "##f$preflop##",
        "",
        "##f$flop##",
        "When !f$deeppot_live_enabled Fold Force",
        f"When dll$deeppot_action = {EMERGENCY_STAY_CODE} {stay_action} Force",
        "When dll$deeppot_action = 0 Fold Force",
    ]

    for spec in specs:
        lines.extend(
            [
                f"When f$sit_{spec.scenario_name}",
                f"\tWhen f${spec.list_name} {stay_action} Force",
                "\tWhen Others Fold Force",
            ]
        )
    lines.extend(
        [
            "When Others Fold Force",
            "",
            "##f$turn##",
            "",
            "##f$river##",
            "",
            "////////////////////////////////////////////////////////////////////////",
            "// EXPLICIT PUBLIC SITUATIONS — analogous to DeepKK f$sit_* catalogue",
            "////////////////////////////////////////////////////////////////////////",
            "",
        ]
    )

    for spec in specs:
        stay_code = encoded_action_code(spec.num_players, spec.dense_id, stay=True)
        fold_code = -stay_code
        lines.extend(
            [
                f"// N={spec.num_players} actor={spec.actor} dense={spec.dense_id} global_code={stay_code}",
                f"##f$sit_{spec.scenario_name}##",
                f"(dll$deeppot_action = {stay_code}) || (dll$deeppot_action = {fold_code})",
                "",
            ]
        )

    lines.extend(
        [
            "////////////////////////////////////////////////////////////////////////",
            "// EXACT STAY LIST MEMBERSHIP — operational equivalent of DeepKK lists",
            "////////////////////////////////////////////////////////////////////////",
            "",
        ]
    )
    for spec in specs:
        stay_code = encoded_action_code(spec.num_players, spec.dense_id, stay=True)
        lines.extend(
            [
                f"// {spec.scenario_name}: positive code means current exact state is on this STAY list",
                f"##f${spec.list_name}##",
                f"dll$deeppot_action = {stay_code}",
                "",
            ]
        )

    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate DeepPot DeepKK-style OpenHoldem formula")
    ap.add_argument("--out", required=True)
    ap.add_argument("--runtime-manifest-sha256", default="PENDING")
    ap.add_argument("--stay-action", default="BetMax")
    ap.add_argument("--enable-live", action="store_true")
    args = ap.parse_args()
    text = generate_openholdem_formula(
        runtime_manifest_sha256=args.runtime_manifest_sha256,
        stay_action=args.stay_action,
        live_enabled=args.enable_live,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
