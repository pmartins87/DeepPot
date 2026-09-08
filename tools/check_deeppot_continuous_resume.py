from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from deeppot.cards import Card
from deeppot.continuous_training import ContinuousConfig, Task, load_state, save_state
from deeppot.continuous_runner import production_source_sha256
from deeppot.solver import ChanceSampledCFR, InfoNode


def node_tuple(node: InfoNode | None) -> tuple[float, float, float, float, int]:
    if node is None:
        return (0.0, 0.0, 0.0, 0.0, 0)
    return (
        node.regrets[0],
        node.regrets[1],
        node.strategy_sum[0],
        node.strategy_sum[1],
        node.visits,
    )


def main() -> None:
    flop = (Card(14, 0), Card(7, 1), Card(2, 2))
    flop_key = tuple((c.rank, c.suit) for c in flop)
    cfg = ContinuousConfig(seed=123, rake_pct=0.02, rake_cap=None)
    task = Task(n=2, flop_index=0, flop_key=flop_key)
    source_sha = production_source_sha256()

    uninterrupted = ChanceSampledCFR(
        num_players=2,
        flop=flop,
        rake_pct=0.02,
        seed=123,
        cfr_plus=True,
        linear_average=True,
    )
    uninterrupted.solve(120)

    temp = Path(tempfile.mkdtemp(prefix="deeppot_continuous_smoke_"))
    try:
        split = ChanceSampledCFR(
            num_players=2,
            flop=flop,
            rake_pct=0.02,
            seed=123,
            cfr_plus=True,
            linear_average=True,
        )
        split.solve(45)
        save_state(
            root=temp,
            task=task,
            config=cfg,
            source_sha256=source_sha,
            solver=split,
            iterations_completed=45,
        )
        restored, completed = load_state(
            root=temp,
            task=task,
            config=cfg,
            source_sha256=source_sha,
        )
        if completed != 45:
            raise SystemExit(f"FAIL: expected completed=45, got {completed}")
        restored.continue_solve(75, completed_iterations=completed)

        keys = uninterrupted.nodes.keys() | restored.nodes.keys()
        for key in keys:
            if node_tuple(uninterrupted.nodes.get(key)) != node_tuple(restored.nodes.get(key)):
                raise SystemExit(f"FAIL: CFR state diverged at infoset {key}")
        if uninterrupted.rng.getstate() != restored.rng.getstate():
            raise SystemExit("FAIL: RNG state diverged after resume")

        print("DEEPPOT CONTINUOUS RESUME SMOKE: PASS")
        print("  uninterrupted iterations: 120")
        print("  split: 45 + checkpoint/load + 75")
        print("  regrets: exact match")
        print("  linear-average strategy sums: exact match")
        print("  visit counts: exact match")
        print("  RNG state: exact match")
    finally:
        shutil.rmtree(temp, ignore_errors=True)


if __name__ == "__main__":
    main()
