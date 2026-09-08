from __future__ import annotations

from pathlib import Path

from deeppot import continuous_training_fast_v2 as ct
from deeppot.fast_solver_v2 import FastChanceSampledCFRV2


def test_fast_v2_persistent_checkpoint_resume_is_exact(tmp_path: Path) -> None:
    task = ct._all_tasks()[321]
    config = ct.ContinuousConfig(seed=123, rake_pct=0.02, rake_cap=None)
    source_sha = ct._source_sha256()
    flop = ct._cards_from_key(task.flop_key)

    full = FastChanceSampledCFRV2(
        num_players=task.n,
        flop=flop,
        rake_pct=config.rake_pct,
        rake_cap=config.rake_cap,
        seed=config.seed,
        cfr_plus=config.cfr_plus,
        linear_average=config.linear_average,
    )
    full.solve(120)

    split = FastChanceSampledCFRV2(
        num_players=task.n,
        flop=flop,
        rake_pct=config.rake_pct,
        rake_cap=config.rake_cap,
        seed=config.seed,
        cfr_plus=config.cfr_plus,
        linear_average=config.linear_average,
    )
    split.solve(45)
    ct.save_state(
        root=tmp_path,
        task=task,
        config=config,
        source_sha256=source_sha,
        solver=split,
        iterations_completed=45,
    )

    restored, completed = ct.load_state(
        root=tmp_path,
        task=task,
        config=config,
        source_sha256=source_sha,
    )
    assert completed == 45
    restored.continue_solve(75, completed_iterations=completed)

    assert full.rng.getstate() == restored.rng.getstate()
    assert full.nodes.keys() == restored.nodes.keys()
    for key in full.nodes:
        a = full.nodes[key]
        b = restored.nodes[key]
        assert a.visits == b.visits
        assert a.regrets == b.regrets
        assert a.strategy_sum == b.strategy_sum
