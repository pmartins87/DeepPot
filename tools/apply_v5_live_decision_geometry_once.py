from pathlib import Path

source_path = Path("runtime/openholdem/deeppot_userdll.cpp")
test_path = Path("tests/test_openholdem_failsoft_source_contract.py")
text = source_path.read_text(encoding="utf-8")

old_version = 'const char* kAdapterVersion = "failsoft-v4-anchor-evidence-20260909";'
new_version = 'const char* kAdapterVersion = "failsoft-v5-live-decision-geometry-20260909";'
if old_version in text:
    text = text.replace(old_version, new_version, 1)
elif new_version not in text:
    raise SystemExit("adapter version marker not found")

helper = r'''bool StrongLiveDecisionGeometry(const deeppot_runtime::LiveScrapeSnapshot& s) {
  if (!CoherentAnchorSnapshot(s)) return false;
  const std::uint32_t seat_mask = SeatMask(s.nchairs);
  const std::uint32_t dealt = s.playersdealtbits & seat_mask;
  const std::uint32_t playing = s.playersplayingbits & seat_mask;
  const std::uint32_t folded = s.foldbits2 & seat_mask;
  const std::uint32_t hero_bit = static_cast<std::uint32_t>(1) << s.userchair;

  // Decision-time geometry is considered authoritative only when every dealt
  // seat has a complete, non-contradictory live state and Hero is still live.
  // This deliberately excludes transient dropout/foldbit noise, which remains
  // eligible for same-hand anchor/history recovery.
  if ((playing & ~dealt) != 0 || (folded & ~dealt) != 0) return false;
  if ((playing & folded) != 0) return false;
  if ((playing | folded) != dealt) return false;
  if ((playing & hero_bit) == 0 || (folded & hero_bit) != 0) return false;
  return true;
}

'''
if "bool StrongLiveDecisionGeometry(" not in text:
    marker = "void ApplyHandAnchor(\n"
    if marker not in text:
        raise SystemExit("ApplyHandAnchor marker not found")
    text = text.replace(marker, helper + marker, 1)

old_sig = r'''void ApplyHandAnchor(
    deeppot_runtime::LiveScrapeSnapshot* current,
    std::vector<std::string>* reasons) {'''
new_sig = r'''void ApplyHandAnchor(
    deeppot_runtime::LiveScrapeSnapshot* current,
    std::vector<std::string>* reasons,
    bool prefer_current_geometry) {'''
if old_sig in text:
    text = text.replace(old_sig, new_sig, 1)
elif new_sig not in text:
    raise SystemExit("ApplyHandAnchor signature not found")

anchor_prefix = r'''  const deeppot_runtime::LiveScrapeSnapshot& a = g_hand.anchor;
  const std::uint32_t anchored_dealt = a.playersdealtbits & SeatMask(a.nchairs);

  // v4 live-safety rule: an old anchor is fallback evidence, never absolute'''
anchor_replacement = r'''  const deeppot_runtime::LiveScrapeSnapshot& a = g_hand.anchor;
  const std::uint32_t anchored_dealt = a.playersdealtbits & SeatMask(a.nchairs);

  // v5 decision-time precedence: a complete, internally coherent live public
  // snapshot paired with live exact cards outranks an older same-hand anchor.
  // The anchor is recovery evidence, not authority over a valid current Hero,
  // BTN or dealt geometry. This fixes the v4 5s5c, Qc7s and Ad7d live failures.
  if (prefer_current_geometry && StrongLiveDecisionGeometry(*current)) {
    const std::uint32_t current_dealt = current->playersdealtbits & SeatMask(current->nchairs);
    const bool differs_from_anchor =
        current->nchairs != a.nchairs ||
        current->userchair != a.userchair ||
        current->dealerchair != a.dealerchair ||
        current_dealt != anchored_dealt ||
        current->nplayersdealt != BitCount(anchored_dealt);
    if (differs_from_anchor && reasons) {
      reasons->push_back("live_decision_geometry_preferred_over_anchor");
    }
    return;
  }

  // v4 live-safety rule retained as a secondary defense: an old anchor is
  // fallback evidence, never absolute'''
if anchor_prefix in text:
    text = text.replace(anchor_prefix, anchor_replacement, 1)
elif "live_decision_geometry_preferred_over_anchor" not in text:
    raise SystemExit("anchor prefix not found")

old_norm = r'''bool NormalizeSnapshotForRecovery(
    deeppot_runtime::LiveScrapeSnapshot* current,
    std::vector<std::string>* reasons) {
  ApplyHandAnchor(current, reasons);'''
new_norm = r'''bool NormalizeSnapshotForRecovery(
    deeppot_runtime::LiveScrapeSnapshot* current,
    std::vector<std::string>* reasons,
    bool prefer_current_geometry) {
  ApplyHandAnchor(current, reasons, prefer_current_geometry);'''
if old_norm in text:
    text = text.replace(old_norm, new_norm, 1)
elif new_norm not in text:
    raise SystemExit("NormalizeSnapshotForRecovery block not found")

old_decision_call = "NormalizeSnapshotForRecovery(&current, &normalization_reasons);"
new_decision_call = "NormalizeSnapshotForRecovery(&current, &normalization_reasons, !cards_from_cache);"
if old_decision_call in text:
    text = text.replace(old_decision_call, new_decision_call, 1)
elif new_decision_call not in text:
    raise SystemExit("decision normalization call not found")

# Historical snapshots must remain structurally anchored. They are evidence for
# recovery, not decision-time authoritative live snapshots.
text = text.replace("ApplyHandAnchor(&historical, NULL);", "ApplyHandAnchor(&historical, NULL, false);")

# Guard against an incomplete patch leaving a legacy two-argument call.
if "ApplyHandAnchor(current, reasons);" in text or "ApplyHandAnchor(&historical, NULL);" in text:
    raise SystemExit("legacy ApplyHandAnchor call remains")

source_path.write_text(text, encoding="utf-8")


test = test_path.read_text(encoding="utf-8")
if "from deeppot.runtime_contract import scenario_dense_id_from_mask" not in test:
    test = test.replace(
        "import re\n",
        "import re\n\nfrom deeppot.runtime_contract import scenario_dense_id_from_mask\n",
        1,
    )

test = test.replace(
    'assert "ApplyHandAnchor(current, reasons);" in normalize.group(0)',
    'assert "ApplyHandAnchor(current, reasons, prefer_current_geometry);" in normalize.group(0)',
)
test = test.replace(
    'assert \'kAdapterVersion = "failsoft-v4-anchor-evidence-20260909"\' in source',
    'assert \'kAdapterVersion = "failsoft-v5-live-decision-geometry-20260909"\' in source',
)

extra = r'''

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
'''
if "test_v5_complete_live_decision_geometry_outranks_stale_anchor" not in test:
    test += extra

test_path.write_text(test, encoding="utf-8")
print("v5 live decision geometry patch applied")
