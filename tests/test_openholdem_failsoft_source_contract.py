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


def test_same_hand_public_geometry_is_frozen_before_primary_lookup() -> None:
    source = _source()
    assert "HAND_ANCHOR" in source
    assert "dealt_from_hand_anchor" in source
    assert "dealer_from_hand_anchor" in source
    assert "nplayersdealt_from_hand_anchor" in source

    normalize = re.search(
        r"bool NormalizeSnapshotForRecovery\((.*?)\n\}",
        source,
        flags=re.S,
    )
    assert normalize is not None
    assert "ApplyHandAnchor(current, reasons);" in normalize.group(0)


def test_incomplete_prior_action_evidence_is_not_accepted_as_exact_history() -> None:
    source = _source()
    assert "inferred_fold_mask != 0" in source
    assert "deferred_to_policy_recovery" in source
    assert "RecoverPublicStateCandidates(current, g_hand.snapshots, 64)" in source


def test_runtime_identifies_the_deployed_failsoft_generation_in_logs() -> None:
    source = _source()
    assert 'kAdapterVersion = "failsoft-v3-action-history-20260909"' in source
    assert "adapter loaded version=%s" in source
