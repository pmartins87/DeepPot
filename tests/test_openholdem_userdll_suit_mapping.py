from pathlib import Path
import re


def test_openholdem_adapter_uses_stddeck_zero_based_suit_mapping() -> None:
    source = (Path(__file__).resolve().parents[1] / "runtime" / "openholdem" / "deeppot_userdll.cpp").read_text(encoding="utf-8")

    # OpenHoldem/PokerEval StdDeck: H=0,D=1,C=2,S=3.
    # DeepPot exact-state engine: C=0,D=1,H=2,S=3.
    # Adapter mapping therefore must be [2,1,0,3], not +/-1 arithmetic.
    match = re.search(
        r"kOpenHoldemSuitToDeepPot\[4\]\s*=\s*\{\s*2\s*,.*?1\s*,.*?0\s*,.*?3\s*,?\s*\}",
        source,
        flags=re.S,
    )
    assert match is not None
    assert "openholdem_suit < 0 || openholdem_suit > 3" in source
    assert "openholdem_suit - 1" not in source
