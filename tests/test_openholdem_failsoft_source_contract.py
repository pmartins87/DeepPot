from pathlib import Path
import re


def _source() -> str:
    return (
        Path(__file__).resolve().parents[1]
        / "runtime"
        / "openholdem"
        / "deeppot_userdll.cpp"
    ).read_text(encoding="utf-8")


def test_handreset_is_evidence_not_an_unconditional_memory_wipe() -> None:
    source = _source()
    match = re.search(
        r"void __stdcall DLLUpdateOnHandreset\(\) \{(.*?)\n\}",
        source,
        flags=re.S,
    )
    assert match is not None
    body = match.group(1)
    assert "pending_handreset_observations" in body
    assert "CaptureLiveObservation" in body
    assert "FullReset" not in body
    assert "ClearHandData" not in body
    assert "ResetForNewHand" not in body


def test_same_hand_anchor_is_available_but_cannot_override_contradictory_live_action_evidence() -> None:
    source = _source()
    assert "HAND_ANCHOR" in source
    assert "dealt_from_hand_anchor" in source
    assert "dealer_from_hand_anchor" in source
    assert "nplayersdealt_from_hand_anchor" in source
    assert "live_action_evidence" in source
    assert "anchor_rejected_by_live_action_evidence" in source
    assert "live_action_evidence & ~anchored_dealt" in source

    normalize = re.search(
        r"bool NormalizeSnapshotForRecovery\((.*?)\n\}",
        source,
        flags=re.S,
    )
    assert normalize is not None
    assert "ApplyHandAnchor(current, reasons);" in normalize.group(0)


def test_three_v3_live_anchor_poisoning_cases_trigger_v4_rejection_condition() -> None:
    # Exact live cases from the first v3 field test.  The v4 adapter condition is
    # (playersplayingbits | foldbits2) & ~anchor.playersdealtbits != 0.
    # Therefore each stale partial anchor below must be rejected before it can
    # overwrite the coherent decision-time N/dealt geometry.
    cases = [
        # label, stale anchor dealt mask, decision-time playing, decision-time foldbits2
        ("Qc2c/Tc6h9d", 0x07, 0xDF, 0x00),
        ("9s5s/2c8hAh", 0x0F, 0x1E, 0xC1),
        ("Js5d/7sQc8d", 0x3F, 0x9C, 0x43),
    ]
    for label, anchored_dealt, playing, folded in cases:
        live_action_evidence = (playing | folded) & 0xFF
        assert (live_action_evidence & ~anchored_dealt & 0xFF) != 0, label


def test_incomplete_prior_action_evidence_is_not_accepted_as_exact_history() -> None:
    source = _source()
    assert "inferred_fold_mask != 0" in source
    assert "deferred_to_policy_recovery" in source
    assert "RecoverPublicStateCandidates(current, g_hand.snapshots, 64)" in source


def test_runtime_identifies_the_deployed_failsoft_generation_in_logs() -> None:
    source = _source()
    assert 'kAdapterVersion = "failsoft-v4-anchor-evidence-20260909"' in source
    assert "adapter loaded version=%s" in source
