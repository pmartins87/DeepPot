import math

from deeppot.state_space import (
    S4_CYCLE_TYPES,
    decision_scenario_count,
    exact_flop_hole_orbit_count,
    exact_infoset_upper_count,
    exact_state_space_summary,
    fixed_partitioned_states,
)


def test_burnside_fixed_counts() -> None:
    observed = {
        cycle_type: fixed_partitioned_states(cycle_type)
        for cycle_type, _ in S4_CYCLE_TYPES
    }
    assert observed[(1, 1, 1, 1)] == 25_989_600
    assert observed[(2, 1, 1)] == 797_056
    assert observed[(2, 2)] == 0
    assert observed[(3, 1)] == 13_884
    assert observed[(4,)] == 0


def test_exact_flop_hole_orbits() -> None:
    assert exact_flop_hole_orbit_count() == 1_286_792


def test_exact_space_is_larger_than_1755_times_169() -> None:
    summary = exact_state_space_summary()
    assert summary.naive_169_flop_states == 296_595
    assert summary.exact_flop_hole_orbits == 1_286_792
    assert math.isclose(summary.exact_vs_169_ratio, 4.3385492000876615, rel_tol=1e-12)


def test_public_scenario_counts() -> None:
    assert [decision_scenario_count(n) for n in range(2, 9)] == [2, 6, 14, 30, 62, 126, 254]


def test_dense_infoset_upper_counts() -> None:
    expected = {
        2: 2_573_584,
        3: 7_720_752,
        4: 18_015_088,
        5: 38_603_760,
        6: 79_781_104,
        7: 162_135_792,
        8: 326_845_168,
    }
    assert {n: exact_infoset_upper_count(n) for n in range(2, 9)} == expected
