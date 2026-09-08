from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path

from .deepkk_style_evaluator import evaluate_policy_deepkk_style, load_policy_gzip
from .deepkk_style_export import generate_deeppot_txt, write_scenario_catalog_csv
from .multiway_response import parse_flop
from .production import ProductionConfig, run_production


GENERATOR_VERSION = "2026-09-07.deepkk-parity.1"


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _parse_map(text: str, *, value_type=int) -> dict[int, int | float]:
    out: dict[int, int | float] = {}
    for item in text.split(","):
        item = item.strip()
        if not item:
            continue
        n_text, value_text = item.split(":", 1)
        n = int(n_text)
        if not 2 <= n <= 8:
            raise ValueError(f"invalid N in map: {n}")
        out[n] = value_type(value_text)
    missing = [n for n in range(2, 9) if n not in out]
    if missing:
        raise ValueError(f"map missing N values: {missing}")
    return out


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
        "production.py",
        "deepkk_style_evaluator.py",
        "deepkk_style_export.py",
        "deepkk_style_generator.py",
    )
    h = hashlib.sha256()
    for name in names:
        h.update(name.encode("utf-8"))
        h.update((root / name).read_bytes())
    return h.hexdigest()


def _audit_one(job: tuple[int, Path, Path, int, float, int, float, float | None]) -> tuple[list[dict], dict]:
    n, policy_path, meta_path, samples, min_visits, seed, rake_pct, rake_cap = job
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    flop = parse_flop(" ".join(meta["flop"]))
    policy = load_policy_gzip(policy_path)
    rows, summary = evaluate_policy_deepkk_style(
        num_players=n,
        flop=flop,
        policy=policy,
        samples=samples,
        min_effective_visits=min_visits,
        seed=seed + int(meta["flop_index"]) * 1009 + n * 1_000_003,
        rake_pct=rake_pct,
        rake_cap=rake_cap,
    )
    for row in rows:
        row["flop_index"] = int(meta["flop_index"])
        row["flop_id"] = str(meta["flop_id"])
        row["flop"] = " ".join(meta["flop"])
    summary = dict(summary)
    summary.update(
        {
            "num_players": n,
            "flop_index": int(meta["flop_index"]),
            "flop_id": str(meta["flop_id"]),
            "policy_sha256": meta["policy_sha256"],
        }
    )
    return rows, summary


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError("cannot write empty CSV")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run_deepkk_style_generation(
    *,
    out_dir: str | Path,
    iterations_by_n: dict[int, int],
    ev_samples_by_n: dict[int, int],
    min_effective_visits_by_n: dict[int, float],
    seed: int,
    rake_pct: float,
    rake_cap: float | None,
    economy_profile: str,
    solve_workers: int,
    audit_workers: int,
    start_index: int = 0,
    limit: int | None = None,
) -> dict:
    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    source_sha = _source_sha256()
    started = time.time()

    manifest = {
        "generator_version": GENERATOR_VERSION,
        "method": "DeepKK-parity: CFR+ + linear average + EV/CI audit + solver-greedy fallback",
        "source_sha256": source_sha,
        "economy_profile": economy_profile,
        "rake_pct": rake_pct,
        "rake_cap": rake_cap,
        "seed": seed,
        "iterations_by_n": {str(k): int(v) for k, v in iterations_by_n.items()},
        "ev_samples_by_n": {str(k): int(v) for k, v in ev_samples_by_n.items()},
        "min_effective_visits_by_n": {str(k): float(v) for k, v in min_effective_visits_by_n.items()},
        "solve_workers": solve_workers,
        "audit_workers": audit_workers,
        "start_index": start_index,
        "limit": limit,
        "stage": "running",
        "started_at_unix": started,
    }
    _atomic_write(root / "RUN_MANIFEST.json", json.dumps(manifest, indent=2, sort_keys=True))

    all_final_rows: list[dict] = []
    all_audit_summaries: list[dict] = []

    for n in range(2, 9):
        mode_root = root / f"N{n}"
        solve_root = mode_root / "solve"
        config = ProductionConfig(
            num_players=n,
            iterations=int(iterations_by_n[n]),
            seeds=(int(seed),),
            rake_pct=rake_pct,
            rake_cap=rake_cap,
            economy_profile_id=economy_profile,
            require_complete_coverage=True,
        )
        solve_results = run_production(
            config=config,
            out_dir=solve_root,
            workers=solve_workers,
            start_index=start_index,
            limit=limit,
        )

        jobs: list[tuple[int, Path, Path, int, float, int, float, float | None]] = []
        for result in solve_results:
            jobs.append(
                (
                    n,
                    Path(result.policy_path),
                    Path(result.metadata_path),
                    int(ev_samples_by_n[n]),
                    float(min_effective_visits_by_n[n]),
                    int(seed),
                    float(rake_pct),
                    rake_cap,
                )
            )

        mode_rows: list[dict] = []
        mode_summaries: list[dict] = []
        if audit_workers <= 1:
            iterator = (_audit_one(job) for job in jobs)
            for rows, summary in iterator:
                mode_rows.extend(rows)
                mode_summaries.append(summary)
        else:
            with ProcessPoolExecutor(max_workers=audit_workers) as executor:
                futures = [executor.submit(_audit_one, job) for job in jobs]
                for future in as_completed(futures):
                    rows, summary = future.result()
                    mode_rows.extend(rows)
                    mode_summaries.append(summary)

        mode_rows.sort(key=lambda r: (int(r["flop_index"]), int(r["scenario_dense_id"]), int(r["exact_hole_state_id"])))
        mode_summaries.sort(key=lambda r: int(r["flop_index"]))
        _write_csv(mode_root / "final_strategy.csv", mode_rows)
        _atomic_write(mode_root / "ev_audit_summary.json", json.dumps(mode_summaries, indent=2, sort_keys=True))
        all_final_rows.extend(mode_rows)
        all_audit_summaries.extend(mode_summaries)

        manifest[f"N{n}"] = {
            "flops_completed": len(solve_results),
            "final_rows": len(mode_rows),
            "confident_infosets": sum(int(x["confident_best_action_infosets"]) for x in mode_summaries),
            "total_infosets": sum(int(x["total_infosets"]) for x in mode_summaries),
        }
        _atomic_write(root / "RUN_MANIFEST.json", json.dumps(manifest, indent=2, sort_keys=True))

    all_final_rows.sort(
        key=lambda r: (
            int(r["num_players"]),
            int(r["flop_index"]),
            int(r["scenario_dense_id"]),
            int(r["exact_hole_state_id"]),
        )
    )
    _write_csv(root / "final_strategy_reference_all_modes.csv", all_final_rows)
    _atomic_write(root / "ev_audit_summary_all_modes.json", json.dumps(all_audit_summaries, indent=2, sort_keys=True))
    write_scenario_catalog_csv(root / "scenario_catalog_494.csv")
    deeppot_txt = generate_deeppot_txt(root / "final_strategy_reference_all_modes.csv")
    _atomic_write(root / "DeepPot.txt", deeppot_txt)

    outputs = {
        "final_strategy_sha256": hashlib.sha256((root / "final_strategy_reference_all_modes.csv").read_bytes()).hexdigest(),
        "deeppot_txt_sha256": hashlib.sha256((root / "DeepPot.txt").read_bytes()).hexdigest(),
        "scenario_catalog_sha256": hashlib.sha256((root / "scenario_catalog_494.csv").read_bytes()).hexdigest(),
    }
    manifest.update(outputs)
    manifest["stage"] = "completed"
    manifest["completed_at_unix"] = time.time()
    manifest["elapsed_seconds"] = time.time() - started
    _atomic_write(root / "RUN_MANIFEST.json", json.dumps(manifest, indent=2, sort_keys=True))
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser(description="Unified DeepPot generator following the DeepKK production method")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--iterations-map", required=True, help="e.g. 2:20000,3:20000,...,8:20000")
    ap.add_argument("--ev-samples-map", required=True, help="per-flop EV audit samples for N=2..8")
    ap.add_argument("--min-effective-visits-map", required=True, help="minimum effective visits for N=2..8")
    ap.add_argument("--seed", type=int, default=123)
    ap.add_argument("--rake-pct", type=float, required=True)
    ap.add_argument("--rake-cap", type=float, default=None)
    ap.add_argument("--economy-profile", required=True)
    ap.add_argument("--solve-workers", type=int, default=1)
    ap.add_argument("--audit-workers", type=int, default=1)
    ap.add_argument("--start-index", type=int, default=0)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    manifest = run_deepkk_style_generation(
        out_dir=args.out_dir,
        iterations_by_n={k: int(v) for k, v in _parse_map(args.iterations_map, value_type=int).items()},
        ev_samples_by_n={k: int(v) for k, v in _parse_map(args.ev_samples_map, value_type=int).items()},
        min_effective_visits_by_n={k: float(v) for k, v in _parse_map(args.min_effective_visits_map, value_type=float).items()},
        seed=args.seed,
        rake_pct=args.rake_pct,
        rake_cap=args.rake_cap,
        economy_profile=args.economy_profile,
        solve_workers=args.solve_workers,
        audit_workers=args.audit_workers,
        start_index=args.start_index,
        limit=args.limit,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
