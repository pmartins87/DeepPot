from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import statistics
import time
from collections import Counter
from pathlib import Path

from .continuous_training import (
    TOTAL_EXACT_INFOSETS,
    _atomic_write_json,
    _quantile_from_hist,
)
from .openholdem_formula import generate_openholdem_formula


MODE_INFOSETS = {
    2: 2_573_584,
    3: 7_720_752,
    4: 18_015_088,
    5: 38_603_760,
    6: 79_781_104,
    7: 162_135_792,
    8: 326_845_168,
}
MODE_SCENARIOS = {n: (1 << n) - 2 for n in range(2, 9)}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(4 * 1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _safe_name(name: str) -> str:
    name = name.strip()
    if not name:
        raise ValueError("snapshot name must not be empty")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", name):
        raise ValueError("snapshot name may contain only letters, digits, dot, underscore and dash")
    return name


def _xor_bit_count(a: Path, b: Path) -> int:
    if a.stat().st_size != b.stat().st_size:
        raise RuntimeError(f"snapshot bitset size mismatch: {a} vs {b}")
    mismatches = 0
    with a.open("rb") as fa, b.open("rb") as fb:
        while True:
            aa = fa.read(1 << 20)
            bb = fb.read(1 << 20)
            if not aa:
                break
            if len(aa) != len(bb):
                raise RuntimeError("snapshot bitset read mismatch")
            mismatches += int.from_bytes(bytes(x ^ y for x, y in zip(aa, bb)), "little").bit_count()
    return mismatches


def _latest_previous_snapshot(snapshot_root: Path, exclude: Path) -> tuple[Path, dict] | None:
    candidates: list[tuple[float, Path, dict]] = []
    if not snapshot_root.exists():
        return None
    for child in snapshot_root.iterdir():
        if not child.is_dir() or child.resolve() == exclude.resolve():
            continue
        manifest = child / "SNAPSHOT_MANIFEST.json"
        if not manifest.exists():
            continue
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            candidates.append((float(payload.get("created_at_unix", 0.0)), child, payload))
        except Exception:
            continue
    if not candidates:
        return None
    _, path, payload = max(candidates, key=lambda x: x[0])
    return path, payload


def create_snapshot(
    *,
    training_root: Path,
    name: str,
    runtime_index_source: Path,
    stay_action: str = "BetPot",
    live_enabled: bool = True,
) -> dict:
    name = _safe_name(name)
    master_path = training_root / "CONTINUOUS_MANIFEST.json"
    if not master_path.exists():
        raise RuntimeError(f"continuous manifest not found: {master_path}")
    master = json.loads(master_path.read_text(encoding="utf-8"))
    if master.get("stage") not in ("paused", "completed"):
        raise RuntimeError(
            f"training must be safely paused/completed before snapshot; current stage={master.get('stage')!r}"
        )
    if not runtime_index_source.exists():
        raise RuntimeError(f"runtime index not found: {runtime_index_source}")

    snapshot_root = training_root / "snapshots"
    out = snapshot_root / name
    if out.exists():
        raise RuntimeError(f"snapshot already exists and will not be overwritten: {out}")
    runtime = out / "DeepPotRuntime"
    strategy_dir = runtime / "strategy"
    strategy_dir.mkdir(parents=True, exist_ok=False)
    shutil.copy2(runtime_index_source, runtime / "deeppot_runtime_index.bin")

    global_hist: Counter[int] = Counter()
    iterations: list[int] = []
    greedy_stay_total = 0
    mixed_total = 0
    summaries_total = 0
    modes: dict[str, dict] = {}

    for n in range(2, 9):
        summary_dir = training_root / f"N{n}" / "summaries"
        rows = []
        if summary_dir.exists():
            for path in sorted(summary_dir.glob("flop_*.json")):
                row = json.loads(path.read_text(encoding="utf-8"))
                if int(row.get("n", -1)) == n:
                    rows.append((path, row))
        if len(rows) != 1755:
            raise RuntimeError(f"N={n}: snapshot requires 1,755 checkpointed flop states, found {len(rows)}")

        seen_indices = [int(row["flop_index"]) for _, row in rows]
        if seen_indices != list(range(1755)):
            raise RuntimeError(f"N={n}: summary flop indices are incomplete/non-canonical")

        mode_out = strategy_dir / f"N{n}_final.bits"
        with mode_out.open("wb") as fout:
            for summary_file, row in rows:
                if row.get("source_sha256") != master.get("source_sha256"):
                    raise RuntimeError(f"source mismatch in {summary_file}")
                bits_path = Path(row["greedy_bits_file"])
                if not bits_path.exists():
                    raise RuntimeError(f"missing greedy bits: {bits_path}")
                bits = bits_path.read_bytes()
                if hashlib.sha256(bits).hexdigest() != row.get("greedy_bits_sha256"):
                    raise RuntimeError(f"greedy bit hash mismatch: {bits_path}")
                if len(bits) != int(row["greedy_bits_bytes"]):
                    raise RuntimeError(f"greedy bit length mismatch: {bits_path}")
                fout.write(bits)

                for k, count in row.get("visit_histogram", {}).items():
                    global_hist[int(k)] += int(count)
                iterations.append(int(row["iterations_completed"]))
                greedy_stay_total += int(row.get("greedy_stay_infosets", 0))
                mixed_total += int(row.get("average_policy_45_55_infosets", 0))
                summaries_total += int(row.get("expected_infosets", 0))

        if summaries_total > TOTAL_EXACT_INFOSETS:
            raise RuntimeError("snapshot summary infoset count overflow")
        if mode_out.stat().st_size <= 0:
            raise RuntimeError(f"N={n}: empty strategy output")
        modes[str(n)] = {
            "file": f"strategy/N{n}_final.bits",
            "bytes": mode_out.stat().st_size,
            "sha256": _sha256(mode_out),
            "infosets": MODE_INFOSETS[n],
            "scenarios": MODE_SCENARIOS[n],
        }

    if summaries_total != TOTAL_EXACT_INFOSETS:
        raise RuntimeError(f"snapshot exact infoset total mismatch: {summaries_total} != {TOTAL_EXACT_INFOSETS}")
    if sum(global_hist.values()) != TOTAL_EXACT_INFOSETS:
        raise RuntimeError("snapshot visit histogram does not account for every exact infoset")

    runtime_manifest = {
        "format": "DeepPot continuous CFR exact-state runtime snapshot",
        "complete": True,
        "snapshot_name": name,
        "source_continuous_manifest": str(master_path),
        "source_continuous_manifest_sha256": _sha256(master_path),
        "source_training_sha256": master.get("source_sha256"),
        "source_seed": master.get("config", {}).get("seed"),
        "source_economy_profile": "provisional-2pct-uncapped",
        "strategic_card_abstraction": "none",
        "flops": 1755,
        "modes": modes,
        "runtime_index": {
            "file": "deeppot_runtime_index.bin",
            "bytes": (runtime / "deeppot_runtime_index.bin").stat().st_size,
            "sha256": _sha256(runtime / "deeppot_runtime_index.bin"),
        },
        "policy_source": "greedy linear-average CFR policy; no independent EV-audit override",
        "created_at_unix": time.time(),
    }
    runtime_manifest_path = runtime / "deeppot_runtime_manifest.json"
    _atomic_write_json(runtime_manifest_path, runtime_manifest)
    runtime_manifest_sha = _sha256(runtime_manifest_path)

    formula_path = out / f"DeepPot_{name}.txt"
    formula_path.write_text(
        generate_openholdem_formula(
            runtime_manifest_sha256=runtime_manifest_sha,
            stay_action=stay_action,
            live_enabled=live_enabled,
        ),
        encoding="utf-8",
    )

    previous = _latest_previous_snapshot(snapshot_root, out)
    stability = None
    if previous is not None:
        prev_path, prev_manifest = previous
        per_mode = {}
        total_changed = 0
        for n in range(2, 9):
            old_bits = prev_path / "DeepPotRuntime" / "strategy" / f"N{n}_final.bits"
            new_bits = runtime / "strategy" / f"N{n}_final.bits"
            if not old_bits.exists():
                raise RuntimeError(f"previous snapshot lacks N={n} bitset: {old_bits}")
            changed = _xor_bit_count(old_bits, new_bits)
            total_changed += changed
            per_mode[str(n)] = {
                "changed_actions": changed,
                "infosets": MODE_INFOSETS[n],
                "changed_pct": 100.0 * changed / MODE_INFOSETS[n],
            }
        stability = {
            "previous_snapshot": prev_manifest.get("snapshot_name", prev_path.name),
            "changed_actions": total_changed,
            "total_infosets": TOTAL_EXACT_INFOSETS,
            "changed_pct": 100.0 * total_changed / TOTAL_EXACT_INFOSETS,
            "modes": per_mode,
        }

    snapshot_manifest = {
        "format": "DeepPot continuous training snapshot",
        "snapshot_name": name,
        "created_at_unix": time.time(),
        "training_root": str(training_root),
        "training_stage_at_snapshot": master.get("stage"),
        "target_min_visits": int(master.get("target_min_visits_per_infoset", 0)),
        "exact_infosets": TOTAL_EXACT_INFOSETS,
        "visit_depth": {
            "min": min(global_hist) if global_hist else 0,
            "p01": _quantile_from_hist(global_hist, 0.01),
            "p05": _quantile_from_hist(global_hist, 0.05),
            "median": _quantile_from_hist(global_hist, 0.50),
            "mean": sum(k * v for k, v in global_hist.items()) / TOTAL_EXACT_INFOSETS,
            "p95": _quantile_from_hist(global_hist, 0.95),
            "max": max(global_hist) if global_hist else 0,
        },
        "iterations_completed": {
            "min": min(iterations),
            "median": statistics.median(iterations),
            "max": max(iterations),
        },
        "greedy_stay_infosets": greedy_stay_total,
        "greedy_stay_pct": 100.0 * greedy_stay_total / TOTAL_EXACT_INFOSETS,
        "average_policy_45_55_infosets": mixed_total,
        "average_policy_45_55_pct": 100.0 * mixed_total / TOTAL_EXACT_INFOSETS,
        "completion_target_reached": (min(global_hist) if global_hist else 0) >= int(master.get("target_min_visits_per_infoset", 0)),
        "runtime_manifest": str(runtime_manifest_path),
        "runtime_manifest_sha256": runtime_manifest_sha,
        "formula": str(formula_path),
        "formula_sha256": _sha256(formula_path),
        "stability_vs_previous": stability,
        "audit": "not required by the continuous-depth track; independent EV audit remains optional/targeted",
    }
    _atomic_write_json(out / "SNAPSHOT_MANIFEST.json", snapshot_manifest)

    print("DeepPot continuous snapshot created")
    print(f"  name: {name}")
    print(f"  exact infosets: {TOTAL_EXACT_INFOSETS:,}")
    print(
        "  visits: min={min} p05={p05} median={median} mean={mean:.2f} p95={p95} max={max}".format(
            **snapshot_manifest["visit_depth"]
        )
    )
    print(f"  runtime: {runtime}")
    print(f"  formula: {formula_path}")
    if stability is not None:
        print(
            f"  policy changes vs {stability['previous_snapshot']}: "
            f"{stability['changed_actions']:,} ({stability['changed_pct']:.6f}%)"
        )
    print("  Training state was NOT consumed. Resume the master with the same training command.")
    return snapshot_manifest


def main() -> None:
    ap = argparse.ArgumentParser(description="Freeze an arbitrary-time DeepPot continuous CFR snapshot")
    ap.add_argument("--training-root", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--runtime-index", required=True)
    ap.add_argument("--stay-action", default="BetPot")
    ap.add_argument("--disable-live", action="store_true")
    args = ap.parse_args()
    create_snapshot(
        training_root=Path(args.training_root),
        name=args.name,
        runtime_index_source=Path(args.runtime_index),
        stay_action=args.stay_action,
        live_enabled=not args.disable_live,
    )


if __name__ == "__main__":
    main()
