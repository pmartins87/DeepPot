from pathlib import Path
import re

from deeppot.runtime_contract import scenario_dense_id_from_mask


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
    assert "ApplyHandAnchor(current, reasons, prefer_current_geometry);" in normalize.group(0)


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
    assert 'kAdapterVersion = "failsoft-v5-live-decision-geometry-20260909"' in source
    assert "adapter loaded version=%s" in source


def test_v5_complete_live_decision_geometry_outranks_stale_anchor() -> None:
    source = _source()
    assert "StrongLiveDecisionGeometry" in source
    assert "live_decision_geometry_preferred_over_anchor" in source
    assert "prefer_current_geometry && StrongLiveDecisionGeometry(*current)" in source
    assert "NormalizeSnapshotForRecovery(&current, &normalization_reasons, !cards_from_cache)" in source


def test_three_v4_wrong_state_live_cases_reconstruct_to_decision_time_scenarios() -> None:
    # These are the exact decision-time public geometries from the v4 live log.
    # They must never be rewritten by an older Hero/BTN anchor.
    cases = [
        # label, N, actor, prior STAY mask, expected dense scenario
        ("5s5c/ThKc7c", 8, 1, 0b0, 1),
        ("Qc7s/As9dJd", 5, 1, 0b1, 2),
        ("Ad7d/Ks3d5h", 5, 1, 0b0, 1),
    ]
    for label, n, actor, stay_mask, expected in cases:
        assert scenario_dense_id_from_mask(n, actor, stay_mask) == expected, label


def test_v5_strong_live_geometry_accepts_exact_v4_cases_and_anchor_too_large_inverse() -> None:
    def strong(nchairs: int, dealer: int, hero: int, dealt: int, playing: int, folded: int, n: int) -> bool:
        seat_mask = (1 << nchairs) - 1
        dealt &= seat_mask
        playing &= seat_mask
        folded &= seat_mask
        if nchairs < 2 or nchairs > 10 or not (0 <= dealer < nchairs) or not (0 <= hero < nchairs):
            return False
        if dealt.bit_count() != n or not (2 <= n <= 8):
            return False
        if not (dealt & (1 << dealer)) or not (dealt & (1 << hero)):
            return False
        if (playing & ~dealt) or (folded & ~dealt) or (playing & folded):
            return False
        if (playing | folded) != dealt:
            return False
        return bool(playing & (1 << hero)) and not bool(folded & (1 << hero))

    # v4 stale-Hero case, stale-dealer case, and a stale-dealer all-in case.
    assert strong(8, 0, 2, 0xFF, 0xFD, 0x02, 8)
    assert strong(8, 0, 2, 0xA7, 0xA7, 0x00, 5)
    assert strong(8, 0, 2, 0x8F, 0x8D, 0x02, 5)

    # Inverse geometry: even if an old anchor contains MORE dealt players, a
    # complete current decision (here N5) is authoritative and must not expand
    # back to the old N8 anchor.
    stale_anchor_dealt = 0xFF
    current_dealt = 0xA7
    assert stale_anchor_dealt != current_dealt
    assert strong(8, 0, 2, current_dealt, current_dealt, 0x00, 5)
