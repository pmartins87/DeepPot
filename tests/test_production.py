from deeppot.production import ProductionConfig, _selected_flops


def test_production_config_hash_is_stable_and_sensitive() -> None:
    a = ProductionConfig(
        num_players=2,
        iterations=2_000_000,
        seeds=(1, 2, 3),
        rake_pct=0.02,
        rake_cap=None,
        economy_profile_id="provisional-2pct",
    )
    b = ProductionConfig(
        num_players=2,
        iterations=2_000_000,
        seeds=(1, 2, 3),
        rake_pct=0.02,
        rake_cap=None,
        economy_profile_id="provisional-2pct",
    )
    c = ProductionConfig(
        num_players=2,
        iterations=2_000_001,
        seeds=(1, 2, 3),
        rake_pct=0.02,
        rake_cap=None,
        economy_profile_id="provisional-2pct",
    )
    assert a.config_sha256() == b.config_sha256()
    assert a.config_sha256() != c.config_sha256()


def test_selected_flops_are_finite_and_deterministic() -> None:
    first = _selected_flops(0, 3)
    again = _selected_flops(0, 3)
    assert first == again
    assert [i for i, _ in first] == [0, 1, 2]
    assert len(first) == 3
