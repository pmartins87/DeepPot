from deeppot.openholdem_formula import generate_openholdem_formula
from deeppot.runtime_contract import TOTAL_SCENARIOS


def test_formula_has_exactly_494_situations_and_494_stay_membership_functions() -> None:
    text = generate_openholdem_formula(
        runtime_manifest_sha256="abc123",
        stay_action="BetPot",
        live_enabled=False,
    )
    assert TOTAL_SCENARIOS == 494
    assert text.count("##f$sit_") == 494
    assert text.count("##f$list_") == 494
    assert text.count("dll$deeppot_action") >= 988
    assert "dll$deeppot_action = 494" in text
    assert "dll$deeppot_action = -494" in text
    assert "##f$deeppot_live_enabled##\nfalse" in text
    assert "When !f$deeppot_live_enabled Fold Force" in text
    assert "Runtime manifest SHA256: abc123" in text


def test_formula_enables_live_only_explicitly() -> None:
    disabled = generate_openholdem_formula(live_enabled=False)
    enabled = generate_openholdem_formula(live_enabled=True)
    assert "##f$deeppot_live_enabled##\nfalse" in disabled
    assert "##f$deeppot_live_enabled##\ntrue" in enabled
