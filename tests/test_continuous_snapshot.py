from pathlib import Path

from deeppot.continuous_snapshot import _safe_name, _xor_bit_count


def test_xor_bit_count_counts_exact_changed_actions(tmp_path: Path) -> None:
    a = tmp_path / "a.bits"
    b = tmp_path / "b.bits"
    a.write_bytes(bytes([0b00000000, 0b10101010, 0b11110000]))
    b.write_bytes(bytes([0b00000101, 0b10101110, 0b11000011]))
    expected = (0b00000101).bit_count() + (0b00000100).bit_count() + (0b00110011).bit_count()
    assert _xor_bit_count(a, b) == expected


def test_snapshot_name_policy() -> None:
    assert _safe_name("V1.1") == "V1.1"
    assert _safe_name("V1_2-test") == "V1_2-test"
