from deeppot.openholdem_shadow_formula import generate_shadow_formula


def test_shadow_formula_queries_dll_only_from_debug_and_has_no_action_commands() -> None:
    text = generate_shadow_formula(runtime_manifest_sha256="abc123")
    assert "##f$debug##" in text
    assert "= dll$deeppot_action" in text
    assert "Runtime manifest SHA256: abc123" in text

    forbidden = (
        "Fold Force",
        "Call Force",
        "BetPot Force",
        "BetMax Force",
        "Raise",
        "Allin",
    )
    for token in forbidden:
        assert token not in text

    assert text.count("dll$deeppot_action") == 2  # notes + one debug expression
