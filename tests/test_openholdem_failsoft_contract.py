from pathlib import Path
import re


def _source() -> str:
    return (
        Path(__file__).resolve().parents[1]
        / "runtime"
        / "openholdem"
        / "deeppot_userdll.cpp"
    ).read_text(encoding="utf-8")


def test_openholdem_adapter_uses_stddeck_zero_based_suit_mapping() -> None:
    source = _source()

    # OpenHoldem/PokerEval StdDeck: H=0,D=1,C=2,S=3.
    # DeepPot exact-state engine: C=0,D=1,H=2,S=3.
    # Adapter mapping therefore must be [2,1,0,3], independent of formatting.
    body = re.search(
        r"kOpenHoldemSuitToDeepPot\[4\]\s*=\s*\{(.*?)\};",
        source,
        flags=re.S,
    )
    assert body is not None
    values = [int(x) for x in re.findall(r"\d+", body.group(1))]
    assert values == [2, 1, 0, 3]
    assert "openholdem_suit < 0 || openholdem_suit > 3" in source
    assert "openholdem_suit - 1" not in source


def test_v4_must_not_allow_stale_anchor_to_override_stronger_live_action_evidence() -> None:
    """Regression contract from the first v3 controlled live run.

    Qc2c froze N=3 before a coherent N=7 decision; 9s5s froze N=4 before N=7;
    Js5d froze N=6 before N=8. A future adapter must explicitly reject/bypass a
    hand anchor when live playing/fold evidence contains a seat not represented
    in the anchor's dealt mask.
    """
    source = _source()
    assert "anchor_rejected_by_live_action_evidence" in source
    assert "live_action_evidence" in source
    assert "~anchored_dealt" in source or "& ~anchored_dealt" in source
