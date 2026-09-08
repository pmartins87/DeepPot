from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path

from .cards import Card, canonical_flop_id, enumerate_canonical_flops
from .deepkk_style_compact import evaluate_policy_deepkk_style_compact
from .deepkk_style_export import enumerate_all_scenarios, write_scenario_catalog_csv
from .exact_index import ExactFlopHoleIndex
from .solver import ChanceSampledCFR
from .state_space import decision_scenario_count


STREAMING_GENERATOR_VERSION = "2026-09-08.deepkk-parity.1"
BIT_VECTOR_NAMES = ("final", "solver", "confident", "low_coverage")


@dataclass(frozen=True)
class ModeConfig:
    num_players: int
    iterations: int
    audit_samples: int
    min_effective_visits: float
    seed: int
    rake_pct: float
    rake_cap: float | None
    economy_profile: str

    def stable_dict(self) -> dict:
        return asdict(self)

    def config_sha256(self) -> str:
        raw = json.dumps(self.stable_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class FlopCheckpoint:
    num_players: int
    flop_index: int
    flop_id: str
    hole_state_count: int
    public_scenarios: int
    expected_infosets: int
    vector_bytes: int
    solve_seconds: float
    audit_seconds: float
    config_sha256: str
    source_sha256: str
    blob_sha256: str
    audit_summary: dict
    status: str


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


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
        "multiway_response.py",
        "deepkk_style_compact.py",
        "deepkk_style_export.py",
        "deepkk_style_streaming.py",
    )
    h = hashlib.sha256()
    for name in names:
        h.update(name.encode("utf-8"))
        h.update((root / name).read_bytes())
    return h.hexdigest()


def _cards_from_key(key: tuple[tuple[int, int], ...]) -> tuple[Card, Card, Card]:
    if len(key) != 3:
        raise ValueError("flop key must contain exactly three cards")
    return tuple(Card(rank, suit) for rank, suit in key)  # type: ignore[return-value]


def _checkpoint_paths(root: Path, n: int, flop_index: int, flop_id: str) -> tuple[Path, Path]:
    base = root / f"N{n}" / "checkpoints"
    stem = f"flop_{flop_index:04d}_{flop_id}"
    return base / f"{stem}.bin", base / f"{stem}.json"


def _checkpoint_valid(meta_path: Path, blob_path: Path, *, config_sha: str, source_sha: str) -> bool:
    if not meta_path.exists() or not blob_path.exists():
        return False
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    if meta.get("config_sha256") != config_sha or meta.get("source_sha256") != source_sha:
        return False
    if meta.get("stage") != "completed":
        return False
    return hashlib.sha256(blob_path.read_bytes()).hexdigest() == meta.get("blob_sha256")


def _solve_audit_one(
    args: tuple[
        str,
        int,
        tuple[tuple[int, int], ...],
        ModeConfig,
        str,
    ]
) -> FlopCheckpoint:
    root_text, flop_index, flop_key, config, source_sha = args
    root = Path(root_text)
    flop = _cards_from_key(flop_key)
    flop_id = canonical_flop_id(flop)
    config_sha = config.config_sha256()
    blob_path, meta_path = _checkpoint_paths(root, config.num_players, flop_index, flop_id)

    if _checkpoint_valid(meta_path, blob_path, config_sha=config_sha, source_sha=source_sha):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return FlopCheckpoint(
            num_players=config.num_players,
            flop_index=flop_index,
            flop_id=flop_id,
            hole_state_count=int(meta["hole_state_count"]),
            public_scenarios=int(meta["public_scenarios"]),
            expected_infosets=int(meta["expected_infosets"]),
            vector_bytes=int(meta["vector_bytes"]),
            solve_seconds=float(meta.get("solve_seconds", 0.0)),
            audit_seconds=float(meta.get("audit_seconds", 0.0)),
            config_sha256=config_sha,
            source_sha256=source_sha,
            blob_sha256=str(meta["blob_sha256"]),
            audit_summary=dict(meta["audit_summary"]),
            status="skipped_existing",
        )

    exact = ExactFlopHoleIndex.build(flop)
    h = len(exact)
    scenarios = decision_scenario_count(config.num_players)
    expected = h * scenarios

    solve_started = time.perf_counter()
    solved = ChanceSampledCFR(
        num_players=config.num_players,
        flop=flop,
        rake_pct=config.rake_pct,
        rake_cap=config.rake_cap,
        seed=config.seed,
        cfr_plus=True,
        linear_average=True,
    ).solve(config.iterations)
    solve_seconds = time.perf_counter() - solve_started

    if solved.hole_state_count != h:
        raise AssertionError("solver/exact-index hole-state mismatch")
    if len(solved.nodes) != expected or set(solved.nodes) != set(range(expected)):
        raise RuntimeError(
            f"incomplete exact coverage N={config.num_players} flop={flop_id}: "
            f"{len(solved.nodes)}/{expected}"
        )
    policy = solved.average_policy()

    audit_started = time.perf_counter()
    audit = evaluate_policy_deepkk_style_compact(
        num_players=config.num_players,
        flop=flop,
        policy=policy,
        samples=config.audit_samples,
        min_effective_visits=config.min_effective_visits,
        seed=config.seed + 50_000_000 + flop_index * 1009 + config.num_players * 1_000_003,
        rake_pct=config.rake_pct,
        rake_cap=config.rake_cap,
    )
    audit_seconds = time.perf_counter() - audit_started

    if audit.expected_infosets != expected:
        raise AssertionError("audit/solver infoset-width mismatch")
    vector_bytes = (expected + 7) // 8
    vectors = (
        audit.final_stay_bits,
        audit.solver_stay_bits,
        audit.confident_bits,
        audit.low_coverage_bits,
    )
    if any(len(v) != vector_bytes for v in vectors):
        raise AssertionError("unexpected compact vector width")
    blob = b"".join(vectors)
    blob_sha = hashlib.sha256(blob).hexdigest()
    _atomic_write_bytes(blob_path, blob)

    meta = {
        "stage": "completed",
        "streaming_generator_version": STREAMING_GENERATOR_VERSION,
        "num_players": config.num_players,
        "flop_index": flop_index,
        "flop": [str(c) for c in flop],
        "flop_id": flop_id,
        "hole_state_count": h,
        "public_scenarios": scenarios,
        "expected_infosets": expected,
        "vector_bytes": vector_bytes,
        "vector_order": list(BIT_VECTOR_NAMES),
        "solve_seconds": solve_seconds,
        "audit_seconds": audit_seconds,
        "config": config.stable_dict(),
        "config_sha256": config_sha,
        "source_sha256": source_sha,
        "blob_sha256": blob_sha,
        "audit_summary": audit.summary,
    }
    _atomic_write_text(meta_path, json.dumps(meta, indent=2, sort_keys=True))

    return FlopCheckpoint(
        num_players=config.num_players,
        flop_index=flop_index,
        flop_id=flop_id,
        hole_state_count=h,
        public_scenarios=scenarios,
        expected_infosets=expected,
        vector_bytes=vector_bytes,
        solve_seconds=solve_seconds,
        audit_seconds=audit_seconds,
        config_sha256=config_sha,
        source_sha256=source_sha,
        blob_sha256=blob_sha,
        audit_summary=audit.summary,
        status="completed",
    )


def _selected_flops(start_index: int, limit: int | None) -> list[tuple[int, tuple[tuple[int, int], ...]]]:
    flops = list(enumerate_canonical_flops())
    if not 0 <= start_index < len(flops):
        raise ValueError("start_index out of range")
    end = len(flops) if limit is None else min(len(flops), start_index + limit)
    if end <= start_index:
        raise ValueError("empty flop selection")
    return [(i, flops[i]) for i in range(start_index, end)]


def _merge_mode(
    *,
    root: Path,
    config: ModeConfig,
    selected: list[tuple[int, tuple[tuple[int, int], ...]]],
    source_sha: str,
) -> dict:
    mode = root / f"N{config.num_players}"
    compiled = mode / "compiled"
    compiled.mkdir(parents=True, exist_ok=True)
    config_sha = config.config_sha256()

    out_paths = {
        name: compiled / f"N{config.num_players}_{name}.bits"
        for name in BIT_VECTOR_NAMES
    }
    tmp_paths = {name: path.with_suffix(path.suffix + ".tmp") for name, path in out_paths.items()}
    handles = {name: tmp.open("wb") for name, tmp in tmp_paths.items()}
    index_rows: list[dict] = []
    byte_offsets = {name: 0 for name in BIT_VECTOR_NAMES}
    summaries: list[dict] = []

    try:
        for flop_index, flop_key in selected:
            flop = _cards_from_key(flop_key)
            flop_id = canonical_flop_id(flop)
            blob_path, meta_path = _checkpoint_paths(root, config.num_players, flop_index, flop_id)
            if not _checkpoint_valid(meta_path, blob_path, config_sha=config_sha, source_sha=source_sha):
                raise RuntimeError(f"missing/invalid checkpoint N={config.num_players} flop={flop_index}")
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            vector_bytes = int(meta["vector_bytes"])
            blob = blob_path.read_bytes()
            if len(blob) != vector_bytes * len(BIT_VECTOR_NAMES):
                raise RuntimeError("checkpoint blob length mismatch")

            row = {
                "flop_index": flop_index,
                "flop_id": flop_id,
                "flop": meta["flop"],
                "hole_state_count": int(meta["hole_state_count"]),
                "public_scenarios": int(meta["public_scenarios"]),
                "expected_infosets": int(meta["expected_infosets"]),
                "vector_bytes": vector_bytes,
                "bit_key_formula": "scenario_dense_id * hole_state_count + exact_hole_state_id",
                "offset_bytes": dict(byte_offsets),
            }
            index_rows.append(row)
            summaries.append({
                "flop_index": flop_index,
                "flop_id": flop_id,
                **dict(meta["audit_summary"]),
            })

            for i, name in enumerate(BIT_VECTOR_NAMES):
                chunk = blob[i * vector_bytes : (i + 1) * vector_bytes]
                handles[name].write(chunk)
                byte_offsets[name] += len(chunk)
    finally:
        for handle in handles.values():
            handle.close()

    for name in BIT_VECTOR_NAMES:
        os.replace(tmp_paths[name], out_paths[name])

    index_payload = {
        "format": "DeepPot dense exact-state mode bitsets",
        "version": STREAMING_GENERATOR_VERSION,
        "num_players": config.num_players,
        "config": config.stable_dict(),
        "config_sha256": config_sha,
        "source_sha256": source_sha,
        "selection_start_index": selected[0][0],
        "selection_flops": len(selected),
        "total_canonical_flops": 1755,
        "complete_mode": len(selected) == 1755 and selected[0][0] == 0,
        "bit_value": "1=STAY, 0=FOLD for final/solver; 1=true for confidence flags",
        "flops": index_rows,
        "files": {
            name: {
                "file": out_paths[name].name,
                "bytes": out_paths[name].stat().st_size,
                "sha256": hashlib.sha256(out_paths[name].read_bytes()).hexdigest(),
            }
            for name in BIT_VECTOR_NAMES
        },
    }
    _atomic_write_text(compiled / f"N{config.num_players}_index.json", json.dumps(index_payload, indent=2, sort_keys=True))
    _atomic_write_text(mode / "audit_summary.json", json.dumps(summaries, indent=2, sort_keys=True))

    return {
        "num_players": config.num_players,
        "flops": len(selected),
        "expected_infosets": sum(int(x["expected_infosets"]) for x in index_rows),
        "confident_infosets": sum(int(x["confident_best_action_infosets"]) for x in summaries),
        "low_coverage_infosets": sum(int(x["low_coverage_infosets"]) for x in summaries),
        "final_stay_infosets": sum(int(x["final_stay_infosets"]) for x in summaries),
        "confident_ev_overrides": sum(int(x["confident_ev_overrides"]) for x in summaries),
        "compiled_index": str(compiled / f"N{config.num_players}_index.json"),
        "compiled_files": {name: str(path) for name, path in out_paths.items()},
    }


def _generate_math_txt(root: Path, mode_results: dict[int, dict]) -> str:
    lines = [
        "##notes##",
        "// ============================================================================",
        "// DEEPPOT MATHEMATICAL BASE — DeepKK-PARITY PRODUCTION SOURCE",
        "// ============================================================================",
        "// Strategy method: CFR+ + linear average + EV/CI95 audit.",
        "// Final decision rule: confident EV-best action, else solver-average greedy.",
        "// Binary strategic actions: FOLD or POT/STAY.",
        "// Exactly 494 public scenarios across N=2..8.",
        "// Each named list below is represented losslessly by the compiled exact-state",
        "// bitset for that N. This is necessary because native OpenPPL 169-hand lists",
        "// cannot encode flop-relative exact states without losing information.",
        "// The operational OpenHoldem layer will query the same generated list by",
        "// (N, scenario_dense_id, canonical_flop_index, exact_hole_state_id).",
        "// ============================================================================",
        "",
    ]
    for spec in enumerate_all_scenarios():
        mode = mode_results[spec.num_players]
        rel = Path(mode["compiled_files"]["final"]).relative_to(root).as_posix()
        lines.extend([
            f"// actor={spec.actor} history={''.join('S' if a.value == 'STAY' else 'F' for a in spec.prior_actions) or 'ROOT'}",
            f"##{spec.list_name}##",
            f"// compiled_list_file={rel}",
            f"// scenario_dense_id={spec.dense_id}",
            "// bit_key=scenario_dense_id * hole_state_count + exact_hole_state_id",
            "// flop byte offset and hole_state_count are in the matching N*_index.json",
            "",
        ])
    return "\n".join(lines).rstrip() + "\n"


def run_streaming_deepkk_parity(
    *,
    out_dir: str | Path,
    players: tuple[int, ...],
    iterations: int,
    audit_samples: int,
    min_effective_visits: float,
    seed: int,
    rake_pct: float,
    rake_cap: float | None,
    economy_profile: str,
    workers: int,
    start_index: int = 0,
    limit: int | None = None,
) -> dict:
    if iterations <= 0 or audit_samples <= 0:
        raise ValueError("iterations and audit_samples must be positive")
    if min_effective_visits < 0.0:
        raise ValueError("min_effective_visits must be non-negative")
    if workers <= 0:
        raise ValueError("workers must be positive")
    if not players or any(n < 2 or n > 8 for n in players):
        raise ValueError("players must be a non-empty subset of 2..8")

    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    selected = _selected_flops(start_index, limit)
    source_sha = _source_sha256()
    started = time.time()

    manifest = {
        "stage": "running",
        "streaming_generator_version": STREAMING_GENERATOR_VERSION,
        "method": "DeepKK parity: CFR+ + linear average + EV/CI95 audit + solver-greedy fallback",
        "source_sha256": source_sha,
        "players": list(players),
        "iterations_per_flop": iterations,
        "audit_samples_per_flop": audit_samples,
        "min_effective_visits": min_effective_visits,
        "seed": seed,
        "rake_pct": rake_pct,
        "rake_cap": rake_cap,
        "economy_profile": economy_profile,
        "workers": workers,
        "start_index": start_index,
        "limit": limit,
        "selected_flops": len(selected),
        "started_at_unix": started,
        "mode_results": {},
    }
    _atomic_write_text(root / "RUN_MANIFEST.json", json.dumps(manifest, indent=2, sort_keys=True))

    mode_results: dict[int, dict] = {}
    for n in players:
        config = ModeConfig(
            num_players=n,
            iterations=iterations,
            audit_samples=audit_samples,
            min_effective_visits=min_effective_visits,
            seed=seed,
            rake_pct=rake_pct,
            rake_cap=rake_cap,
            economy_profile=economy_profile,
        )
        jobs = [(str(root), i, key, config, source_sha) for i, key in selected]
        completed: list[FlopCheckpoint] = []

        if workers == 1:
            iterator = (_solve_audit_one(job) for job in jobs)
            for result in iterator:
                completed.append(result)
                manifest["current_mode"] = n
                manifest["current_mode_completed_flops"] = len(completed)
                _atomic_write_text(root / "RUN_MANIFEST.json", json.dumps(manifest, indent=2, sort_keys=True))
        else:
            with ProcessPoolExecutor(max_workers=workers) as executor:
                futures = [executor.submit(_solve_audit_one, job) for job in jobs]
                for future in as_completed(futures):
                    result = future.result()
                    completed.append(result)
                    manifest["current_mode"] = n
                    manifest["current_mode_completed_flops"] = len(completed)
                    _atomic_write_text(root / "RUN_MANIFEST.json", json.dumps(manifest, indent=2, sort_keys=True))

        completed.sort(key=lambda x: x.flop_index)
        if len(completed) != len(selected):
            raise RuntimeError(f"mode N={n} ended incomplete")
        mode_result = _merge_mode(root=root, config=config, selected=selected, source_sha=source_sha)
        mode_result["solve_seconds_sum"] = sum(x.solve_seconds for x in completed)
        mode_result["audit_seconds_sum"] = sum(x.audit_seconds for x in completed)
        mode_results[n] = mode_result
        manifest["mode_results"][str(n)] = mode_result
        _atomic_write_text(root / "RUN_MANIFEST.json", json.dumps(manifest, indent=2, sort_keys=True))

    write_scenario_catalog_csv(root / "scenario_catalog_494.csv")
    if tuple(players) == tuple(range(2, 9)):
        _atomic_write_text(root / "DeepPot.txt", _generate_math_txt(root, mode_results))

    manifest["stage"] = "completed"
    manifest["completed_at_unix"] = time.time()
    manifest["elapsed_seconds"] = time.time() - started
    manifest.pop("current_mode", None)
    manifest.pop("current_mode_completed_flops", None)
    manifest["scenario_catalog_sha256"] = hashlib.sha256((root / "scenario_catalog_494.csv").read_bytes()).hexdigest()
    if (root / "DeepPot.txt").exists():
        manifest["deeppot_txt_sha256"] = hashlib.sha256((root / "DeepPot.txt").read_bytes()).hexdigest()
    _atomic_write_text(root / "RUN_MANIFEST.json", json.dumps(manifest, indent=2, sort_keys=True))
    return manifest


def _parse_players(text: str) -> tuple[int, ...]:
    values = tuple(sorted({int(x.strip()) for x in text.split(",") if x.strip()}))
    if not values or any(n < 2 or n > 8 for n in values):
        raise ValueError("players must be comma-separated values from 2 through 8")
    return values


def main() -> None:
    default_workers = max(1, ((os.cpu_count() or 8) // 2) - 1)
    ap = argparse.ArgumentParser(description="Resumable Ryzen trainer using the DeepKK production method")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--players", default="2,3,4,5,6,7,8")
    ap.add_argument("--iterations", type=int, default=20_000)
    ap.add_argument("--audit-samples", type=int, default=50_000)
    ap.add_argument("--min-effective-visits", type=float, default=25.0)
    ap.add_argument("--seed", type=int, default=123)
    ap.add_argument("--rake-pct", type=float, default=0.02)
    ap.add_argument("--rake-cap", type=float, default=None)
    ap.add_argument("--economy-profile", default="provisional-2pct-uncapped")
    ap.add_argument("--workers", type=int, default=default_workers)
    ap.add_argument("--start-index", type=int, default=0)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    result = run_streaming_deepkk_parity(
        out_dir=args.out_dir,
        players=_parse_players(args.players),
        iterations=args.iterations,
        audit_samples=args.audit_samples,
        min_effective_visits=args.min_effective_visits,
        seed=args.seed,
        rake_pct=args.rake_pct,
        rake_cap=args.rake_cap,
        economy_profile=args.economy_profile,
        workers=args.workers,
        start_index=args.start_index,
        limit=args.limit,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
