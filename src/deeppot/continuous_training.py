from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import os
import shutil
import signal
import statistics
import struct
import sys
import time
from array import array
from collections import Counter, deque
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .cards import Card, canonical_flop_id, enumerate_canonical_flops
from .solver import ChanceSampledCFR, InfoNode
from .state_space import decision_scenario_count


CONTINUOUS_VERSION = "2026-09-08.continuous-cfr.1"
STATE_MAGIC = b"DPCFRS1\0"
TOTAL_EXACT_INFOSETS = 635_675_248
STATE_BYTES_PER_INFOSET = 8 * 4 + 4  # regrets[2], strategy_sum[2], visits uint32
DEFAULT_TARGET_MIN_VISITS = 1000
DEFAULT_CHUNK_ITERATIONS = 50_000


@dataclass(frozen=True)
class ContinuousConfig:
    seed: int = 123
    rake_pct: float = 0.02
    rake_cap: float | None = None
    cfr_plus: bool = True
    linear_average: bool = True

    def stable_dict(self) -> dict:
        return {
            "seed": self.seed,
            "rake_pct": self.rake_pct,
            "rake_cap": self.rake_cap,
            "cfr_plus": self.cfr_plus,
            "linear_average": self.linear_average,
        }


@dataclass(frozen=True)
class Task:
    n: int
    flop_index: int
    flop_key: tuple[tuple[int, int], ...]


def _cards_from_key(key: Sequence[tuple[int, int]]) -> tuple[Card, Card, Card]:
    if len(key) != 3:
        raise ValueError("flop key must contain exactly three cards")
    return tuple(Card(rank, suit) for rank, suit in key)  # type: ignore[return-value]


def _source_sha256() -> str:
    root = Path(__file__).resolve().parent
    names = (
        "cards.py",
        "economics.py",
        "evaluator.py",
        "exact_index.py",
        "game.py",
        "scenarios.py",
        "solver.py",
        "state_space.py",
        "continuous_training.py",
    )
    h = hashlib.sha256()
    for name in names:
        h.update(name.encode("utf-8"))
        h.update((root / name).read_bytes())
    return h.hexdigest()


def _task_config_sha256(task: Task, config: ContinuousConfig) -> str:
    payload = {
        "continuous_version": CONTINUOUS_VERSION,
        "n": task.n,
        "flop_index": task.flop_index,
        "flop_key": task.flop_key,
        **config.stable_dict(),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _stem(task: Task) -> str:
    flop_id = canonical_flop_id(_cards_from_key(task.flop_key))
    return f"flop_{task.flop_index:04d}_{flop_id}"


def state_path(root: Path, task: Task) -> Path:
    return root / f"N{task.n}" / "states" / f"{_stem(task)}.dpcfr"


def greedy_path(root: Path, task: Task) -> Path:
    return root / f"N{task.n}" / "greedy" / f"{_stem(task)}.bits"


def summary_path(root: Path, task: Task) -> Path:
    return root / f"N{task.n}" / "summaries" / f"{_stem(task)}.json"


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _quantile_from_hist(hist: Counter[int], q: float) -> int:
    if not hist:
        return 0
    total = sum(hist.values())
    if total <= 0:
        return 0
    rank = max(0, min(total - 1, int(math.floor(q * (total - 1)))))
    seen = 0
    for value in sorted(hist):
        seen += hist[value]
        if seen > rank:
            return int(value)
    return int(max(hist))


def _greedy_and_stats(solver: ChanceSampledCFR, expected: int) -> tuple[bytes, dict, tuple[array, array, array, array, array]]:
    regret_fold = array("d")
    regret_stay = array("d")
    sum_fold = array("d")
    sum_stay = array("d")
    visits = array("I")
    bits = bytearray((expected + 7) // 8)
    hist: Counter[int] = Counter()
    stay_count = 0
    mixed_45_55 = 0
    visit_sum = 0

    for key in range(expected):
        node = solver.nodes.get(key)
        if node is None:
            rf = rs = sf = ss = 0.0
            v = 0
        else:
            rf = float(node.regrets[0])
            rs = float(node.regrets[1])
            sf = float(node.strategy_sum[0])
            ss = float(node.strategy_sum[1])
            v = int(node.visits)
        regret_fold.append(rf)
        regret_stay.append(rs)
        sum_fold.append(sf)
        sum_stay.append(ss)
        visits.append(v)
        hist[v] += 1
        visit_sum += v

        # Original average_policy() returns (0.5, 0.5) for zero sum and the
        # production greedy rule uses STAY when p_stay >= 0.5. Comparing sums
        # therefore reproduces the original exact tie behavior.
        if ss >= sf:
            bits[key >> 3] |= 1 << (key & 7)
            stay_count += 1
        total = sf + ss
        p_stay = 0.5 if total <= 0.0 else ss / total
        if 0.45 <= p_stay <= 0.55:
            mixed_45_55 += 1

    stats = {
        "visit_min": min(hist) if hist else 0,
        "visit_p01": _quantile_from_hist(hist, 0.01),
        "visit_p05": _quantile_from_hist(hist, 0.05),
        "visit_median": _quantile_from_hist(hist, 0.50),
        "visit_mean": visit_sum / max(1, expected),
        "visit_p95": _quantile_from_hist(hist, 0.95),
        "visit_max": max(hist) if hist else 0,
        "visit_sum": visit_sum,
        "visit_histogram": {str(k): int(v) for k, v in sorted(hist.items())},
        "greedy_stay_infosets": stay_count,
        "greedy_stay_pct": 100.0 * stay_count / max(1, expected),
        "average_policy_45_55_infosets": mixed_45_55,
        "average_policy_45_55_pct": 100.0 * mixed_45_55 / max(1, expected),
    }
    return bytes(bits), stats, (regret_fold, regret_stay, sum_fold, sum_stay, visits)


def save_state(
    *,
    root: Path,
    task: Task,
    config: ContinuousConfig,
    source_sha256: str,
    solver: ChanceSampledCFR,
    iterations_completed: int,
) -> dict:
    scenarios = decision_scenario_count(task.n)
    h = solver.hole_state_count
    expected = scenarios * h
    bits, stats, arrays = _greedy_and_stats(solver, expected)
    task_sha = _task_config_sha256(task, config)

    header = {
        "format": "DeepPot resumable CFR state",
        "continuous_version": CONTINUOUS_VERSION,
        "source_sha256": source_sha256,
        "task_config_sha256": task_sha,
        "n": task.n,
        "flop_index": task.flop_index,
        "flop_key": [list(x) for x in task.flop_key],
        "flop_id": canonical_flop_id(_cards_from_key(task.flop_key)),
        "hole_state_count": h,
        "public_scenarios": scenarios,
        "expected_infosets": expected,
        "iterations_completed": int(iterations_completed),
        "config": config.stable_dict(),
        "rng_state_repr": repr(solver.rng.getstate()),
        "array_order": ["regret_fold_f64", "regret_stay_f64", "strategy_sum_fold_f64", "strategy_sum_stay_f64", "visits_u32"],
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
        "format": "DeepPot continuous task summary",
        "continuous_version": CONTINUOUS_VERSION,
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
) -> tuple[ChanceSampledCFR, int]:
    flop = _cards_from_key(task.flop_key)
    solver = ChanceSampledCFR(
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
            raise RuntimeError(f"invalid continuous-state magic: {spath}")
        raw_len = f.read(4)
        if len(raw_len) != 4:
            raise RuntimeError(f"truncated continuous-state header: {spath}")
        header_len = struct.unpack("<I", raw_len)[0]
        header = json.loads(f.read(header_len).decode("utf-8"))

        expected = decision_scenario_count(task.n) * solver.hole_state_count
        checks = {
            "continuous_version": CONTINUOUS_VERSION,
            "source_sha256": source_sha256,
            "task_config_sha256": _task_config_sha256(task, config),
            "n": task.n,
            "flop_index": task.flop_index,
            "hole_state_count": solver.hole_state_count,
            "expected_infosets": expected,
        }
        for name, wanted in checks.items():
            if header.get(name) != wanted:
                raise RuntimeError(f"continuous-state mismatch {name}: {header.get(name)!r} != {wanted!r} ({spath})")

        arrays: list[array] = []
        for typecode in ("d", "d", "d", "d", "I"):
            values = array(typecode)
            try:
                values.fromfile(f, expected)
            except EOFError as exc:
                raise RuntimeError(f"truncated continuous-state arrays: {spath}") from exc
            if sys.byteorder != "little":
                values.byteswap()
            arrays.append(values)
        if f.read(1):
            raise RuntimeError(f"continuous-state has unexpected trailing data: {spath}")

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


def _worker_init() -> None:
    if hasattr(signal, "SIGINT"):
        signal.signal(signal.SIGINT, signal.SIG_IGN)


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


def _all_tasks() -> list[Task]:
    flops = list(enumerate_canonical_flops())
    tasks: list[Task] = []
    # Interleave N=2..8 by flop so an arbitrary-time snapshot does not spend its
    # first hours deepening only the low-N modes.
    for flop_index, flop_key in enumerate(flops):
        for n in range(2, 9):
            tasks.append(Task(n=n, flop_index=flop_index, flop_key=tuple(flop_key)))
    return tasks


def _load_summary(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _progress_payload(
    *,
    root: Path,
    summaries: dict[tuple[int, int], dict],
    source_sha256: str,
    config: ContinuousConfig,
    target_min_visits: int,
    chunk_iterations: int,
    workers: int,
    stage: str,
    started_at_unix: float,
    stop_reason: str = "",
) -> dict:
    tasks_with_state = len(summaries)
    target_reached = sum(1 for s in summaries.values() if int(s.get("visit_min", 0)) >= target_min_visits)
    total_visit_sum = sum(int(s.get("visit_sum", 0)) for s in summaries.values())
    minima = [0] * (12_285 - tasks_with_state) + [int(s.get("visit_min", 0)) for s in summaries.values()]
    iterations = [0] * (12_285 - tasks_with_state) + [int(s.get("iterations_completed", 0)) for s in summaries.values()]
    infosets_materialized = sum(int(s.get("expected_infosets", 0)) for s in summaries.values())

    return {
        "format": "DeepPot continuous CFR master manifest",
        "continuous_version": CONTINUOUS_VERSION,
        "stage": stage,
        "stop_reason": stop_reason,
        "source_sha256": source_sha256,
        "config": config.stable_dict(),
        "target_min_visits_per_infoset": target_min_visits,
        "chunk_iterations": chunk_iterations,
        "workers": workers,
        "tasks_total": 12_285,
        "tasks_with_state": tasks_with_state,
        "tasks_target_reached": target_reached,
        "total_exact_infosets": TOTAL_EXACT_INFOSETS,
        "infosets_materialized_in_summaries": infosets_materialized,
        "weighted_mean_training_visits": total_visit_sum / TOTAL_EXACT_INFOSETS,
        "task_min_visit_global": min(minima) if minima else 0,
        "task_min_visit_median": statistics.median(minima) if minima else 0,
        "iterations_completed_min": min(iterations) if iterations else 0,
        "iterations_completed_median": statistics.median(iterations) if iterations else 0,
        "iterations_completed_max": max(iterations) if iterations else 0,
        "estimated_full_state_bytes": TOTAL_EXACT_INFOSETS * STATE_BYTES_PER_INFOSET,
        "estimated_full_state_gib": TOTAL_EXACT_INFOSETS * STATE_BYTES_PER_INFOSET / (1024 ** 3),
        "started_at_unix": started_at_unix,
        "updated_at_unix": time.time(),
        "policy": {
            "audit_required_for_snapshot": False,
            "snapshot_action": "greedy linear-average CFR policy",
            "completion_gate": "every exact infoset visit_count >= target_min_visits",
            "validation": "visit depth + cross-snapshot policy stability; independent EV audit optional/targeted",
        },
        "resume": "Run the same command again. Existing per-flop CFR/RNG states are restored exactly.",
    }


def _write_manifest(root: Path, payload: dict) -> None:
    _atomic_write_json(root / "CONTINUOUS_MANIFEST.json", payload)


def run_continuous(
    *,
    root: Path,
    target_min_visits: int,
    chunk_iterations: int,
    workers: int,
    config: ContinuousConfig,
    max_wall_hours: float,
    min_free_gib: float,
) -> dict:
    if target_min_visits <= 0:
        raise ValueError("target_min_visits must be > 0")
    if chunk_iterations <= 0:
        raise ValueError("chunk_iterations must be > 0")
    if workers <= 0:
        raise ValueError("workers must be > 0")
    root.mkdir(parents=True, exist_ok=True)

    free_gib = shutil.disk_usage(root).free / (1024 ** 3)
    if free_gib < min_free_gib:
        raise RuntimeError(f"insufficient free disk: {free_gib:.2f} GiB < required safety floor {min_free_gib:.2f} GiB")

    source_sha = _source_sha256()
    tasks = _all_tasks()
    summaries: dict[tuple[int, int], dict] = {}
    pending: deque[Task] = deque()
    for task in tasks:
        s = _load_summary(summary_path(root, task))
        if (
            s is not None
            and s.get("source_sha256") == source_sha
            and s.get("task_config_sha256") == _task_config_sha256(task, config)
        ):
            summaries[(task.n, task.flop_index)] = s
            if int(s.get("visit_min", 0)) < target_min_visits:
                pending.append(task)
        else:
            pending.append(task)

    started = time.time()
    stop_requested = False
    stop_reason = ""

    def request_stop(_signum=None, _frame=None) -> None:
        nonlocal stop_requested, stop_reason
        if not stop_requested:
            stop_requested = True
            stop_reason = "user_interrupt"
            print("\nDeepPot: pause requested. No new chunks will start; active chunks will finish and checkpoint safely.", flush=True)

    previous_handler = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, request_stop)

    manifest = _progress_payload(
        root=root,
        summaries=summaries,
        source_sha256=source_sha,
        config=config,
        target_min_visits=target_min_visits,
        chunk_iterations=chunk_iterations,
        workers=workers,
        stage="running",
        started_at_unix=started,
    )
    _write_manifest(root, manifest)

    print("DeepPot CONTINUOUS exact CFR training")
    print(f"  root: {root}")
    print(f"  target: every exact infoset >= {target_min_visits} visits")
    print(f"  chunk: {chunk_iterations:,} iterations per flop-task checkpoint")
    print(f"  workers: {workers}")
    print(f"  tasks: 12,285 | infosets: {TOTAL_EXACT_INFOSETS:,}")
    print(f"  full persistent-state estimate: {manifest['estimated_full_state_gib']:.2f} GiB")
    print("  Ctrl+C = graceful pause; rerun the same command = exact resume")
    print("  EV audit: disabled by design for this deep track; snapshot stability is measured separately")

    completed_chunks = 0
    deadline = None if max_wall_hours <= 0 else time.monotonic() + max_wall_hours * 3600.0
    active: dict[object, Task] = {}
    error: BaseException | None = None

    try:
        with ProcessPoolExecutor(max_workers=workers, initializer=_worker_init) as pool:
            while pending or active:
                if deadline is not None and time.monotonic() >= deadline and not stop_requested:
                    stop_requested = True
                    stop_reason = "max_wall_hours"
                    print("DeepPot: requested wall-time reached; draining active chunks safely.", flush=True)

                while pending and len(active) < workers and not stop_requested:
                    task = pending.popleft()
                    fut = pool.submit(
                        train_one_chunk,
                        (str(root), task, config, source_sha, chunk_iterations, target_min_visits),
                    )
                    active[fut] = task

                if not active:
                    break

                done, _ = wait(tuple(active), timeout=1.0, return_when=FIRST_COMPLETED)
                if not done:
                    continue

                for fut in done:
                    task = active.pop(fut)
                    try:
                        summary = fut.result()
                    except BaseException as exc:
                        error = exc
                        stop_requested = True
                        stop_reason = f"worker_error:{type(exc).__name__}"
                        continue
                    summaries[(task.n, task.flop_index)] = summary
                    completed_chunks += 1
                    reached = int(summary.get("visit_min", 0)) >= target_min_visits
                    if not reached and not stop_requested:
                        pending.append(task)

                    if reached or completed_chunks % 25 == 0:
                        p = _progress_payload(
                            root=root,
                            summaries=summaries,
                            source_sha256=source_sha,
                            config=config,
                            target_min_visits=target_min_visits,
                            chunk_iterations=chunk_iterations,
                            workers=workers,
                            stage="running",
                            started_at_unix=started,
                            stop_reason=stop_reason,
                        )
                        _write_manifest(root, p)
                        print(
                            f"  chunks={completed_chunks:,} target_tasks={p['tasks_target_reached']:,}/12,285 "
                            f"mean_visits={p['weighted_mean_training_visits']:.2f} "
                            f"task_min_median={p['task_min_visit_median']}",
                            flush=True,
                        )

            if error is not None:
                raise error
    finally:
        signal.signal(signal.SIGINT, previous_handler)

    target_reached = sum(1 for s in summaries.values() if int(s.get("visit_min", 0)) >= target_min_visits)
    if target_reached == 12_285:
        stage = "completed"
        stop_reason = "target_reached_all_infosets"
    elif stop_requested:
        stage = "paused"
    else:
        stage = "paused"
        stop_reason = stop_reason or "queue_drained_without_target"

    final = _progress_payload(
        root=root,
        summaries=summaries,
        source_sha256=source_sha,
        config=config,
        target_min_visits=target_min_visits,
        chunk_iterations=chunk_iterations,
        workers=workers,
        stage=stage,
        started_at_unix=started,
        stop_reason=stop_reason,
    )
    _write_manifest(root, final)
    print(f"DeepPot continuous stage: {stage.upper()}")
    print(f"  target tasks: {final['tasks_target_reached']:,}/12,285")
    print(f"  weighted mean visits: {final['weighted_mean_training_visits']:.2f}")
    print(f"  task min-visit median: {final['task_min_visit_median']}")
    if stage == "paused":
        print("  SAFE TO CLOSE. Run the same command later to resume exactly.")
    return final


def main() -> None:
    ap = argparse.ArgumentParser(description="DeepPot interruptible/resumable exact CFR deep training")
    ap.add_argument("--out", required=True)
    ap.add_argument("--target-min-visits", type=int, default=DEFAULT_TARGET_MIN_VISITS)
    ap.add_argument("--chunk-iterations", type=int, default=DEFAULT_CHUNK_ITERATIONS)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--seed", type=int, default=123)
    ap.add_argument("--rake", type=float, default=0.02)
    ap.add_argument("--rake-cap", type=float, default=None)
    ap.add_argument("--max-wall-hours", type=float, default=0.0, help="0 = unlimited; positive value pauses safely after this many hours")
    ap.add_argument("--min-free-gib", type=float, default=30.0)
    args = ap.parse_args()

    run_continuous(
        root=Path(args.out),
        target_min_visits=args.target_min_visits,
        chunk_iterations=args.chunk_iterations,
        workers=args.workers,
        config=ContinuousConfig(seed=args.seed, rake_pct=args.rake, rake_cap=args.rake_cap),
        max_wall_hours=args.max_wall_hours,
        min_free_gib=args.min_free_gib,
    )


if __name__ == "__main__":
    main()
