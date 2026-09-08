from deeppot.worker_benchmark import default_worker_candidates, spread_indices


def test_default_candidates_match_32_thread_ryzen_protocol():
    assert default_worker_candidates(32) == (15, 23, 31)


def test_spread_indices_cover_full_range_without_duplicates():
    values = spread_indices(1755, 64)
    assert len(values) == 64
    assert len(set(values)) == 64
    assert values[0] == 0
    assert values[-1] == 1754
    assert list(values) == sorted(values)
