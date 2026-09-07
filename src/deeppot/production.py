from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from .cards import Card, canonical_flop_id, enumerate_canonical_flops
from .exact_index import ExactFlopHoleIndex
from .solver import ChanceSampledCFR
from .state_space import decision_scenario_count

PRODUCTION_RUNNER_VERSION = "2026-09-07.1"


@dataclass(frozen=True)
class ProductionConfig:
    num_players: int
    iterations: int
    seeds: tuple[int, ...]
    rake_pct: float
    rake_cap: float | None
    economy_profile_id: str
    require_complete_coverage: bool = True

    def validate(self) -> None:
        if not 2 <= self.num_players <= 8:
            raise ValueError("num_players must be between 2 and 8")
        if self.iterations <= 0:
            raise ValueError("iterations must be positive")
        if not self.seeds:
            raise ValueError("at least one seed is required")
        if len(set(self.seeds)) != len(self.seeds):
            raise ValueError("seeds must be unique")
        if not 0.0 <= self.rake_pct < 1.0:
            raise ValueError("rake_pct must be in [0, 1)")
        if self.rake_cap is not None and self.rake_cap < 0.0:
            raise ValueError("rake_cap must be non-negative")
        if not self.economy_profile_id.strip():
            raise ValueError("economy_profile_id must be non-empty")

    def stable_dict(self) -> dict:
        return {
            "num_players": self.num_players,
            "iterations": self.iterations,
            "seeds": list(self.seeds),
            "rake_pct": self.rake_pct,
            "rake_cap": self.rake_cap,
            "economy_profile_id": self.economy_profile_id,
            "require_complete_coverage": self.require_complete_coverage,
            "strategic_card_abstraction": "none",
            "exact_symmetry_reduction": "global_suit_isomorphism_only",
            "runner_version": PRODUCTION_RUNNER_VERSION,
        }

    def config_sha256(self) -> str:
        payload = json.dumps(self.stable_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class FlopShardResult:
    flop_index: int
    flop_id: str
    exact_hole_states: int
    public_scenarios: int
    expected_infosets: int
    exported_infosets: int
    solve_seconds: float
    policy_path: str
    metadata_path: str
    status: str


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
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
        "production.py",
    )
    h = hashlib.sha256()
    for name in names:
        h.update(name.encode("utf-8"))
        h.update((root / name).read_bytes())
    return h.hexdigest()


def _cards_from_flop_key(key: tuple[tuple[int, int], ...]) -> tuple[Card, Card, Card]:
    if len(key) != 3:
        raise ValueError("canonical flop key must contain three cards")
    return tuple(Card(rank, suit) for rank, suit in key)  # type: ignore[return-value]


def _flop_shard_paths(root: Path, config: ProductionConfig, flop_index: int, flop_id: str) -> tuple[Path, Path]:
    mode = root / f"N{config.num_players}"
    stem = f"flop_{flop_index:04d}_{flop_id}"
    return mode / f"{stem}.csv.gz", mode / f"{stem}.meta.json"


def _metadata_matches(path: Path, *, config_sha: str, source_sha: str) -> bool:
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    return (
        data.get("stage") == "completed"
        and data.get("config_sha256") == config_sha
        and data.get("source_sha256") == source_sha
    )


def _write_policy_gzip(
    path: Path,
    *,
    p_stay_sum: list[float],
    visits_sum: list[int],
    seed_count: int,
    hole_state_count: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "infoset_key",
            "public_scenario_id",
            "exact_hole_state_id",
            "p_fold",
            "p_stay",
            "visits",
        ])
        for key, total_stay in enumerate(p_stay_sum):
            p_stay = total_stay / seed_count
            p_fold = 1.0 - p_stay
            public_id, hole_id = divmod(key, hole_state_count)
            writer.writerow([
                key,
                public_id,
                hole_id,
                f"{p_fold:.12g}",
                f"{p_stay:.12g}",
                visits_sum[key],
            ])
    os.replace(tmp, path)


def _solve_flop_worker(args: tuple[int, tuple[tuple[int, int], ...], ProductionConfig, str, str, str]) -> FlopShardResult:
    flop_index, flop_key, config, out_dir_text, config_sha, source_sha = args
    config.validate()
    out_dir = Path(out_dir_text)
    flop = _cards_from_flop_key(flop_key)
    flop_id = canonical_flop_id(flop)
    policy_path, meta_path = _flop_shard_paths(out_dir, config, flop_index, flop_id)

    if _metadata_matches(meta_path, config_sha=config_sha, source_sha=source_sha) and policy_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return FlopShardResult(
            flop_index=flop_index,
            flop_id=flop_id,
            exact_hole_states=int(meta["exact_hole_states"]),
            public_scenarios=int(meta["public_scenarios"]),
            expected_infosets=int(meta["expected_infosets"]),
            exported_infosets=int(meta["exported_infosets"]),
            solve_seconds=float(meta.get("solve_seconds", 0.0)),
            policy_path=str(policy_path),
            metadata_path=str(meta_path),
            status="skipped_existing",
        )

    exact_index = ExactFlopHoleIndex.build(flop)
    hole_count = len(exact_index)
    scenarios = decision_scenario_count(config.num_players)
    expected = hole_count * scenarios
    p_stay_sum = [0.0] * expected
    visits_sum = [0] * expected

    started = time.perf_counter()
    for seed in config.seeds:
        result = ChanceSampledCFR(
            num_players=config.num_players,
            flop=flop,
            rake_pct=config.rake_pct,
            rake_cap=config.rake_cap,
            seed=seed,
            cfr_plus=True,
            linear_average=True,
        ).solve(config.iterations)

        if result.hole_state_count != hole_count:
            raise AssertionError("solver/index hole-state count mismatch")
        if config.require_complete_coverage:
            if len(result.nodes) != expected or set(result.nodes) != set(range(expected)):
                raise RuntimeError(
                    f"incomplete exact coverage on flop {flop_id}, seed {seed}: "
                    f"{len(result.nodes)}/{expected} infosets"
                )

        for key, node in result.nodes.items():
            if key < 0 or key >= expected:
                raise AssertionError("solver produced out-of-range dense infoset key")
            p_stay_sum[key] += node.average_strategy()[1]
            visits_sum[key] += node.visits

    solve_seconds = time.perf_counter() - started
    exported = sum(1 for visits in visits_sum if visits > 0)
    if config.require_complete_coverage and exported != expected:
        raise RuntimeError(f"consensus export coverage incomplete: {exported}/{expected}")

    _write_policy_gzip(
        policy_path,
        p_stay_sum=p_stay_sum,
        visits_sum=visits_sum,
        seed_count=len(config.seeds),
        hole_state_count=hole_count,
    )

    policy_sha = hashlib.sha256(policy_path.read_bytes()).hexdigest()
    metadata = {
        "stage": "completed",
        "runner_version": PRODUCTION_RUNNER_VERSION,
        "source_sha256": source_sha,
        "config_sha256": config_sha,
        "config": config.stable_dict(),
        "flop_index": flop_index,
        "flop": [str(card) for card in flop],
        "flop_id": flop_id,
        "exact_hole_states": hole_count,
        "public_scenarios": scenarios,
        "expected_infosets": expected,
        "exported_infosets": exported,
        "solve_seconds": solve_seconds,
        "policy_sha256": policy_sha,
        "policy_file": policy_path.name,
    }
    _atomic_write_text(meta_path, json.dumps(metadata, indent=2, sort_keys=True))

    return FlopShardResult(
        flop_index=flop_index,
        flop_id=flop_id,
        exact_hole_states=hole_count,
        public_scenarios=scenarios,
        expected_infosets=expected,
        exported_infosets=exported,
        solve_seconds=solve_seconds,
        policy_path=str(policy_path),
        metadata_path=str(meta_path),
        status="completed",
    )


def _selected_flops(start_index: int, limit: int | None) -> list[tuple[int, tuple[tuple[int, int], ...]]]:
    flops = list(enumerate_canonical_flops())
    if start_index < 0 or start_index >= len(flops):
        raise ValueError("start_index out of range")
    end = len(flops) if limit is None else min(len(flops), start_index + limit)
    return [(i, flops[i]) for i in range(start_index, end)]


def run_production(
    *,
    config: ProductionConfig,
    out_dir: str | Path,
    workers: int,
    start_index: int = 0,
    limit: int | None = None,
) -> list[FlopShardResult]:
    config.validate()
    if workers <= 0:
        raise ValueError("workers must be positive")
    if limit is not None and limit <= 0:
        raise ValueError("limit must be positive when supplied")

    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    selected = _selected_flops(start_index, limit)
    source_sha = _source_sha256()
    config_sha = config.config_sha256()
    manifest_path = root / "RUN_MANIFEST.json"

    manifest = {
        "stage": "running",
        "runner_version": PRODUCTION_RUNNER_VERSION,
        "source_sha256": source_sha,
        "config_sha256": config_sha,
        "config": config.stable_dict(),
        "workers": workers,
        "start_index": start_index,
        "limit": limit,
        "target_flops": len(selected),
        "completed_indices": [],
        "started_at_unix": time.time(),
    }
    _atomic_write_text(manifest_path, json.dumps(manifest, indent=2, sort_keys=True))

    jobs = [
        (i, key, config, str(root), config_sha, source_sha)
        for i, key in selected
    ]
    results: list[FlopShardResult] = []

    if workers == 1:
        iterator: Iterable[FlopShardResult] = (_solve_flop_worker(job) for job in jobs)
        for result in iterator:
            results.append(result)
            manifest["completed_indices"] = sorted(r.flop_index for r in results)
            manifest["completed_flops"] = len(results)
            _atomic_write_text(manifest_path, json.dumps(manifest, indent=2, sort_keys=True))
    else:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(_solve_flop_worker, job): job[0] for job in jobs}
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                manifest["completed_indices"] = sorted(r.flop_index for r in results)
                manifest["completed_flops"] = len(results)
                _atomic_write_text(manifest_path, json.dumps(manifest, indent=2, sort_keys=True))

    results.sort(key=lambda r: r.flop_index)
    manifest["stage"] = "completed"
    manifest["completed_at_unix"] = time.time()
    manifest["completed_flops"] = len(results)
    manifest["completed_indices"] = [r.flop_index for r in results]
    manifest["shards"] = [asdict(r) for r in results]
    _atomic_write_text(manifest_path, json.dumps(manifest, indent=2, sort_keys=True))
    return results


def main() -> None:
    ap = argparse.ArgumentParser(description="DeepPot resumable exact all-flop production runner")
    ap.add_argument("--players", type=int, required=True)
    ap.add_argument("--iterations", type=int, required=True)
    ap.add_argument("--seeds", default="1,2,3")
    ap.add_argument("--rake-pct", type=float, required=True)
    ap.add_argument("--rake-cap", type=float, default=None)
    ap.add_argument("--economy-profile", required=True)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--start-index", type=int, default=0)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    seeds = tuple(int(x.strip()) for x in args.seeds.split(",") if x.strip())
    config = ProductionConfig(
        num_players=args.players,
        iterations=args.iterations,
        seeds=seeds,
        rake_pct=args.rake_pct,
        rake_cap=args.rake_cap,
        economy_profile_id=args.economy_profile,
        require_complete_coverage=True,
    )
    results = run_production(
        config=config,
        out_dir=args.out_dir,
        workers=args.workers,
        start_index=args.start_index,
        limit=args.limit,
    )
    print(json.dumps([asdict(result) for result in results], indent=2))


if __name__ == "__main__":
    main()
