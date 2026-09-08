from __future__ import annotations

from pathlib import Path

from deeppot.cards import Card
from deeppot.continuous_training import (
    ContinuousConfig,
    Task,
    _source_sha256,
    load_state,
    save_state,
)
from deeppot.solver import ChanceSampledCFR, InfoNode


FLOP = (Card(14, 0), Card(7, 1), Card(2, 2))
FLOP_KEY = tuple((c.rank, c.suit) for c in FLOP)


def _node_tuple(node: InfoNode | None) -> tuple[float, float, float, float, int]:
    if node is None:
        return (0.0, 0.0, 0.0, 0.0, 0)
    return (
        node.regrets[0],
        node.regrets[1],
        node.strategy_sum[0],
        node.strategy_sum[1],
        node.visits,
    )


def test_continuous_resume_matches_uninterrupted_exactly(tmp_path: Path) -> None:
    cfg = ContinuousConfig(seed=123, rake_pct=0.02, rake_cap=None)
    task = Task(n=2, flop_index=0, flop_key=FLOP_KEY)
    source_sha = _source_sha256()

    uninterrupted = ChanceSampledCFR(
        num_players=2,
        flop=FLOP,
        rake_pct=0.02,
        seed=123,
        cfr_plus=True,
        linear_average=True,
    )
    uninterrupted.solve(80)

    first = ChanceSampledCFR(
        num_players=2,
        flop=FLOP,
        rake_pct=0.02,
        seed=123,
        cfr_plus=True,
        linear_average=True,
    )
    first.solve(30)
    save_state(
        root=tmp_path,
        task=task,
        config=cfg,
        source_sha256=source_sha,
        solver=first,
        iterations_completed=30,
    )

    resumed, completed = load_state(
        root=tmp_path,
        task=task,
        config=cfg,
        source_sha256=source_sha,
    )
    assert completed == 30
    resumed.continue_solve(50, completed_iterations=completed)

    expected = max(uninterrupted.nodes.keys() | resumed.nodes.keys()) + 1
    for key in range(expected):
        assert _node_tuple(resumed.nodes.get(key)) == _node_tuple(uninterrupted.nodes.get(key))
    assert resumed.rng.getstate() == uninterrupted.rng.getstate()


def test_state_roundtrip_preserves_summary_and_rng(tmp_path: Path) -> None:
    cfg = ContinuousConfig(seed=7, rake_pct=0.02, rake_cap=None)
    task = Task(n=2, flop_index=9, flop_key=FLOP_KEY)
    source_sha = _source_sha256()
    solver = ChanceSampledCFR(num_players=2, flop=FLOP, rake_pct=0.02, seed=7)
    solver.solve(25)

    summary = save_state(
        root=tmp_path,
        task=task,
        config=cfg,
        source_sha256=source_sha,
        solver=solver,
        iterations_completed=25,
    )
    assert summary["iterations_completed"] == 25
    assert summary["expected_infosets"] > 0
    assert summary["greedy_bits_bytes"] > 0
    assert sum(int(v) for v in summary["visit_histogram"].values()) == summary["expected_infosets"]

    restored, completed = load_state(
        root=tmp_path,
        task=task,
        config=cfg,
        source_sha256=source_sha,
    )
    assert completed == 25
    assert restored.rng.getstate() == solver.rng.getstate()
    for key in set(restored.nodes) | set(solver.nodes):
        assert _node_tuple(restored.nodes.get(key)) == _node_tuple(solver.nodes.get(key))
