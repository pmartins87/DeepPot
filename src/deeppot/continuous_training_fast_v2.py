from __future__ import annotations

import ast
import hashlib
import json
import os
import struct
import sys
import time
from array import array
from pathlib import Path

from . import continuous_training as base
from .fast_solver_v2 import FastChanceSampledCFRV2
from .solver import InfoNode
from .state_space import decision_scenario_count


CONTINUOUS_VERSION = "2026-09-08.continuous-fast-v2.1"
STATE_MAGIC = b"DPF2RS1\0"
TOTAL_EXACT_INFOSETS = base.TOTAL_EXACT_INFOSETS
STATE_BYTES_PER_INFOSET = base.STATE_BYTES_PER_INFOSET
DEFAULT_TARGET_MIN_VISITS = base.DEFAULT_TARGET_MIN_VISITS
DEFAULT_CHUNK_ITERATIONS = base.DEFAULT_CHUNK_ITERATIONS
ContinuousConfig = base.ContinuousConfig
Task = base.Task

# Reuse the already-audited exact task enumeration and path naming.  The V2
# production root is intentionally different from the paused pilot root.
_all_tasks = base._all_tasks
_cards_from_key = base._cards_from_key
_stem = base._stem
state_path = base.state_path
greedy_path = base.greedy_path
summary_path = base.summary_path
_atomic_write_bytes = base._atomic_write_bytes
_atomic_write_json = base._atomic_write_json
_load_summary = base._load_summary
_worker_init = base._worker_init


def _source_sha256() -> str:
    """Hash every mathematical/state-layout input used by fast-V2 continuous CFR."""
    root = Path(__file__).resolve().parent
    names = (
        "cards.py",
        "economics.py",
        "evaluator.py",
        "exact_index.py",
        "game.py",
        "scenarios.py",
        "solver.py",
        "fast_solver.py",
        "fast_solver_v2.py",
        "state_space.py",
        "continuous_training.py",
        "continuous_training_fast_v2.py",
    )
    h = hashlib.sha256()
    for name in names:
        h.update(name.encode("utf-8"))
        h.update((root / name).read_bytes())
    return h.hexdigest()


def _task_config_sha256(task: Task, config: ContinuousConfig) -> str:
    payload = {
        "continuous_version": CONTINUOUS_VERSION,
        "kernel": "FastChanceSampledCFRV2",
        "n": task.n,
        "flop_index": task.flop_index,
        "flop_key": task.flop_key,
        **config.stable_dict(),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _greedy_and_stats(solver: FastChanceSampledCFRV2, expected: int):
    return base._greedy_and_stats(solver, expected)


def save_state(
    *,
    root: Path,
    task: Task,
    config: ContinuousConfig,
    source_sha256: str,
    solver: FastChanceSampledCFRV2,
    iterations_completed: int,
) -> dict:
    scenarios = decision_scenario_count(task.n)
    h = solver.hole_state_count
    expected = scenarios * h
    bits, stats, arrays = _greedy_and_stats(solver, expected)
    task_sha = _task_config_sha256(task, config)

    header = {
        "format": "DeepPot resumable fast-V2 CFR state",
        "continuous_version": CONTINUOUS_VERSION,
        "kernel": "FastChanceSampledCFRV2",
        "source_sha256": source_sha256,
        "task_config_sha256": task_sha,
        "n": task.n,
        "flop_index": task.flop_index,
        "flop_key": [list(x) for x in task.flop_key],
        "flop_id": base.canonical_flop_id(_cards_from_key(task.flop_key)),
        "hole_state_count": h,
        "public_scenarios": scenarios,
        "expected_infosets": expected,
        "iterations_completed": int(iterations_completed),
        "config": config.stable_dict(),
        "rng_state_repr": repr(solver.rng.getstate()),
        "array_order": [
            "regret_fold_f64",
            "regret_stay_f64",
            "strategy_sum_fold_f64",
            "strategy_sum_stay_f64",
            "visits_u32",
        ],
        "byte_order": "little",
    }
    header_raw = json.dumps(header, sort_keys=True, separators=(",", ":")).encode("utf-8")

    spath = state_path(root, task)
    spath.parent.mkdir(parents=True, exist_ok=True)
    tmp = spath.with_suffix(spath.suffix + ".tmp")
    with tmp.open("wb") as f:
        f.write(STATE_MAGIC)
        f.write(struct.pack("<I", len(header_raw)))
        f.write(header_raw)
        for values in arrays:
            if sys.byteorder != "little":
                values = array(values.typecode, values)
                values.byteswap()
            values.tofile(f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, spath)

    gpath = greedy_path(root, task)
    _atomic_write_bytes(gpath, bits)
    bits_sha = hashlib.sha256(bits).hexdigest()
    summary = {
        "format": "DeepPot fast-V2 continuous task summary",
        "continuous_version": CONTINUOUS_VERSION,
        "kernel": "FastChanceSampledCFRV2",
        "source_sha256": source_sha256,
        "task_config_sha256": task_sha,
        "n": task.n,
        "flop_index": task.flop_index,
        "flop_id": header["flop_id"],
        "hole_state_count": h,
        "public_scenarios": scenarios,
        "expected_infosets": expected,
        "iterations_completed": int(iterations_completed),
        "state_file": str(spath),
        "state_bytes": spath.stat().st_size,
        "greedy_bits_file": str(gpath),
        "greedy_bits_bytes": len(bits),
        "greedy_bits_sha256": bits_sha,
        **stats,
        "updated_at_unix": time.time(),
    }
    _atomic_write_json(summary_path(root, task), summary)
    return summary


def load_state(
    *,
    root: Path,
    task: Task,
    config: ContinuousConfig,
    source_sha256: str,
) -> tuple[FastChanceSampledCFRV2, int]:
    flop = _cards_from_key(task.flop_key)
    solver = FastChanceSampledCFRV2(
        num_players=task.n,
        flop=flop,
        rake_pct=config.rake_pct,
        rake_cap=config.rake_cap,
        seed=config.seed,
        cfr_plus=config.cfr_plus,
        linear_average=config.linear_average,
    )
    spath = state_path(root, task)
    if not spath.exists():
        return solver, 0

    with spath.open("rb") as f:
        if f.read(len(STATE_MAGIC)) != STATE_MAGIC:
            raise RuntimeError(f"invalid fast-V2 continuous-state magic: {spath}")
        raw_len = f.read(4)
        if len(raw_len) != 4:
            raise RuntimeError(f"truncated fast-V2 state header: {spath}")
        header_len = struct.unpack("<I", raw_len)[0]
        header = json.loads(f.read(header_len).decode("utf-8"))

        expected = decision_scenario_count(task.n) * solver.hole_state_count
        checks = {
            "continuous_version": CONTINUOUS_VERSION,
            "kernel": "FastChanceSampledCFRV2",
            "source_sha256": source_sha256,
            "task_config_sha256": _task_config_sha256(task, config),
            "n": task.n,
            "flop_index": task.flop_index,
            "hole_state_count": solver.hole_state_count,
            "expected_infosets": expected,
        }
        for name, wanted in checks.items():
            if header.get(name) != wanted:
                raise RuntimeError(
                    f"fast-V2 continuous-state mismatch {name}: {header.get(name)!r} != {wanted!r} ({spath})"
                )

        arrays: list[array] = []
        for typecode in ("d", "d", "d", "d", "I"):
            values = array(typecode)
            try:
                values.fromfile(f, expected)
            except EOFError as exc:
                raise RuntimeError(f"truncated fast-V2 state arrays: {spath}") from exc
            if sys.byteorder != "little":
                values.byteswap()
            arrays.append(values)
        if f.read(1):
            raise RuntimeError(f"fast-V2 state has unexpected trailing data: {spath}")

    regret_fold, regret_stay, sum_fold, sum_stay, visits = arrays
    nodes: dict[int, InfoNode] = {}
    for key in range(expected):
        v = int(visits[key])
        rf = float(regret_fold[key])
        rs = float(regret_stay[key])
        sf = float(sum_fold[key])
        ss = float(sum_stay[key])
        if v or rf or rs or sf or ss:
            nodes[key] = InfoNode(regrets=[rf, rs], strategy_sum=[sf, ss], visits=v)
    solver.nodes = nodes
    solver.rng.setstate(ast.literal_eval(header["rng_state_repr"]))
    return solver, int(header["iterations_completed"])


def train_one_chunk(args: tuple[str, Task, ContinuousConfig, str, int, int]) -> dict:
    root_text, task, config, source_sha256, chunk_iterations, target_min_visits = args
    root = Path(root_text)
    started = time.perf_counter()
    solver, completed = load_state(root=root, task=task, config=config, source_sha256=source_sha256)

    existing = summary_path(root, task)
    if existing.exists():
        try:
            old = json.loads(existing.read_text(encoding="utf-8"))
            if (
                old.get("source_sha256") == source_sha256
                and old.get("task_config_sha256") == _task_config_sha256(task, config)
                and int(old.get("visit_min", 0)) >= target_min_visits
            ):
                old["chunk_status"] = "already_target"
                old["chunk_seconds"] = time.perf_counter() - started
                return old
        except Exception:
            pass

    if completed == 0:
        result = solver.solve(chunk_iterations)
    else:
        result = solver.continue_solve(chunk_iterations, completed_iterations=completed)
    completed = result.iterations
    summary = save_state(
        root=root,
        task=task,
        config=config,
        source_sha256=source_sha256,
        solver=solver,
        iterations_completed=completed,
    )
    summary["chunk_status"] = "target_reached" if int(summary["visit_min"]) >= target_min_visits else "trained"
    summary["chunk_seconds"] = time.perf_counter() - started
    summary["target_min_visits"] = target_min_visits
    return summary


def _progress_payload(**kwargs) -> dict:
    payload = base._progress_payload(**kwargs)
    payload["continuous_version"] = CONTINUOUS_VERSION
    payload["kernel"] = "FastChanceSampledCFRV2"
    return payload


def _write_manifest(root: Path, payload: dict) -> None:
    base._write_manifest(root, payload)
