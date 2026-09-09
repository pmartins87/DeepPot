from deeppot.openholdem_formula import generate_openholdem_formula
from deeppot.runtime_contract import EMERGENCY_STAY_CODE, TOTAL_SCENARIOS


def test_formula_has_exactly_494_situations_and_494_stay_membership_functions() -> None:
    text = generate_openholdem_formula(
        runtime_manifest_sha256="abc123",
        stay_action="BetMax",
        live_enabled=False,
    )
    assert TOTAL_SCENARIOS == 494
    assert EMERGENCY_STAY_CODE == 495
    assert text.count("##f$sit_") == 494
    assert text.count("##f$list_") == 494
    assert text.count("dll$deeppot_action") >= 988
    assert "dll$deeppot_action = 494" in text
    assert "dll$deeppot_action = -494" in text
    assert "##f$deeppot_live_enabled##\nfalse" in text
    assert "When !f$deeppot_live_enabled Fold Force" in text
    assert "When dll$deeppot_action = 495 BetMax Force" in text
    assert "When dll$deeppot_action = 0 Fold Force" in text
    assert "Runtime manifest SHA256: abc123" in text


def test_formula_default_stay_transport_is_betmax() -> None:
    text = generate_openholdem_formula(live_enabled=True)
    assert "STAY execution token currently configured as: BetMax" in text
    assert "When dll$deeppot_action = 495 BetMax Force" in text


def test_formula_does_not_preempt_dll_fail_soft_recovery_with_scrapeerror() -> None:
    text = generate_openholdem_formula(live_enabled=True)
    flop_router = text.split("##f$flop##", 1)[1].split("##f$turn##", 1)[0]
    assert "f$ScrapeError" not in flop_router
    assert "dll$deeppot_action = 495" in flop_router


def test_formula_enables_live_only_explicitly() -> None:
    disabled = generate_openholdem_formula(live_enabled=False)
    enabled = generate_openholdem_formula(live_enabled=True)
    assert "##f$deeppot_live_enabled##\nfalse" in disabled
    assert "##f$deeppot_live_enabled##\ntrue" in enabled
