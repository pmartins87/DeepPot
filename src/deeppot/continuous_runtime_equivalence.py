from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .cards import enumerate_canonical_flops
from .continuous_training import TOTAL_EXACT_INFOSETS
from .runtime_package import load_runtime_index
from .state_space import decision_scenario_count

EXPECTED_FLOPS = 1755


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _xor_mismatches(a: bytes, b: bytes) -> int:
    if len(a) != len(b):
        raise ValueError(f"byte-length mismatch: {len(a)} != {len(b)}")
    return sum((x ^ y).bit_count() for x, y in zip(a, b))


def verify_continuous_snapshot(
    *,
    training_root: str | Path,
    snapshot_dir: str | Path,
    out_path: str | Path | None = None,
) -> dict:
    training_root = Path(training_root)
    snapshot_dir = Path(snapshot_dir)
    runtime_dir = snapshot_dir / "DeepPotRuntime"

    master_path = training_root / "CONTINUOUS_MANIFEST.json"
    snapshot_manifest_path = snapshot_dir / "SNAPSHOT_MANIFEST.json"
    runtime_manifest_path = runtime_dir / "deeppot_runtime_manifest.json"
    runtime_index_path = runtime_dir / "deeppot_runtime_index.bin"

    for p in (master_path, snapshot_manifest_path, runtime_manifest_path, runtime_index_path):
        if not p.exists():
            raise FileNotFoundError(p)

    master = json.loads(master_path.read_text(encoding="utf-8"))
    snapshot = json.loads(snapshot_manifest_path.read_text(encoding="utf-8"))
    runtime_manifest = json.loads(runtime_manifest_path.read_text(encoding="utf-8"))

    if master.get("stage") not in ("paused", "completed"):
        raise ValueError(f"continuous training is not safely paused/completed: {master.get('stage')!r}")
    if runtime_manifest.get("complete") is not True:
        raise ValueError("runtime manifest is not complete")
    if int(snapshot.get("exact_infosets", -1)) != TOTAL_EXACT_INFOSETS:
        raise ValueError("snapshot exact infoset count mismatch")

    master_sha = _sha256(master_path)
    if runtime_manifest.get("source_continuous_manifest_sha256") != master_sha:
        raise ValueError("snapshot runtime was not built from the current exact continuous manifest")
    if runtime_manifest.get("source_training_sha256") != master.get("source_sha256"):
        raise ValueError("runtime/source training SHA mismatch")

    runtime_index = load_runtime_index(runtime_index_path)
    if len(runtime_index) != EXPECTED_FLOPS:
        raise ValueError(f"runtime index has {len(runtime_index)} flops, expected {EXPECTED_FLOPS}")

    canonical_flops = list(enumerate_canonical_flops())
    if len(canonical_flops) != EXPECTED_FLOPS:
        raise ValueError(f"canonical flop enumerator returned {len(canonical_flops)} flops")

    total_infosets = 0
    total_action_bit_mismatches = 0
    total_index_metadata_mismatches = 0
    modes: list[dict] = []

    for n in range(2, 9):
        summary_dir = training_root / f"N{n}" / "summaries"
        rows: list[tuple[Path, dict]] = []
        for path in summary_dir.glob("flop_*.json"):
            row = json.loads(path.read_text(encoding="utf-8"))
            if int(row.get("n", -1)) == n:
                rows.append((path, row))
        rows.sort(key=lambda x: int(x[1]["flop_index"]))

        if len(rows) != EXPECTED_FLOPS:
            raise ValueError(f"N={n}: expected {EXPECTED_FLOPS} task summaries, found {len(rows)}")
        if [int(r[1]["flop_index"]) for r in rows] != list(range(EXPECTED_FLOPS)):
            raise ValueError(f"N={n}: summary flop indices are incomplete/non-canonical")

        runtime_bits_path = runtime_dir / "strategy" / f"N{n}_final.bits"
        if not runtime_bits_path.exists():
            raise FileNotFoundError(runtime_bits_path)

        expected_mode_bytes = sum(int(row["greedy_bits_bytes"]) for _, row in rows)
        if runtime_bits_path.stat().st_size != expected_mode_bytes:
            raise ValueError(
                f"N={n}: runtime bitset byte length mismatch: "
                f"{runtime_bits_path.stat().st_size} != {expected_mode_bytes}"
            )

        mode_infosets = 0
        index_mismatches = 0
        action_bit_mismatches = 0

        with runtime_bits_path.open("rb") as runtime_f:
            for flop_index, (summary_path, row) in enumerate(rows):
                if row.get("source_sha256") != master.get("source_sha256"):
                    raise ValueError(f"source SHA mismatch in {summary_path}")

                hole_count = int(row["hole_state_count"])
                scenarios = decision_scenario_count(n)
                expected_infosets = scenarios * hole_count
                if int(row["public_scenarios"]) != scenarios:
                    index_mismatches += 1
                if int(row["expected_infosets"]) != expected_infosets:
                    index_mismatches += 1

                rr = runtime_index[flop_index]
                expected_codes = tuple((rank - 2) * 4 + suit for rank, suit in canonical_flops[flop_index])
                if rr.flop_index != flop_index:
                    index_mismatches += 1
                if rr.card_codes != expected_codes:
                    index_mismatches += 1
                if rr.hole_state_count != hole_count:
                    index_mismatches += 1

                source_bits_path = Path(row["greedy_bits_file"])
                if not source_bits_path.exists():
                    raise FileNotFoundError(source_bits_path)
                source_bits = source_bits_path.read_bytes()
                expected_bytes = int(row["greedy_bits_bytes"])
                if len(source_bits) != expected_bytes:
                    raise ValueError(f"greedy source length mismatch: {source_bits_path}")
                if _sha256(source_bits_path) != str(row["greedy_bits_sha256"]):
                    raise ValueError(f"greedy source SHA mismatch: {source_bits_path}")

                runtime_chunk = runtime_f.read(expected_bytes)
                if len(runtime_chunk) != expected_bytes:
                    raise ValueError(f"N={n}: truncated runtime bitset at flop {flop_index}")
                action_bit_mismatches += _xor_mismatches(source_bits, runtime_chunk)
                mode_infosets += expected_infosets

            if runtime_f.read(1):
                raise ValueError(f"N={n}: unexpected trailing runtime bytes")

        actual_runtime_sha = _sha256(runtime_bits_path)
        mode_manifest = runtime_manifest.get("modes", {}).get(str(n), {})
        if int(mode_manifest.get("infosets", -1)) != mode_infosets:
            index_mismatches += 1
        if int(mode_manifest.get("bytes", -1)) != runtime_bits_path.stat().st_size:
            index_mismatches += 1
        if str(mode_manifest.get("sha256", "")) != actual_runtime_sha:
            index_mismatches += 1
        if int(mode_manifest.get("scenarios", -1)) != decision_scenario_count(n):
            index_mismatches += 1

        modes.append(
            {
                "N": n,
                "flops": EXPECTED_FLOPS,
                "infosets": mode_infosets,
                "runtime_bytes": runtime_bits_path.stat().st_size,
                "runtime_sha256": actual_runtime_sha,
                "action_bit_mismatches": action_bit_mismatches,
                "index_metadata_mismatches": index_mismatches,
            }
        )
        total_infosets += mode_infosets
        total_action_bit_mismatches += action_bit_mismatches
        total_index_metadata_mismatches += index_mismatches

    if total_infosets != TOTAL_EXACT_INFOSETS:
        raise ValueError(f"total infosets mismatch: {total_infosets} != {TOTAL_EXACT_INFOSETS}")

    runtime_manifest_sha = _sha256(runtime_manifest_path)
    snapshot_manifest_sha = _sha256(snapshot_manifest_path)
    result = {
        "format": "DeepPot continuous SEL release mathematical-to-runtime equivalence",
        "stage": "PASS" if total_action_bit_mismatches == 0 and total_index_metadata_mismatches == 0 else "FAIL",
        "snapshot_name": snapshot.get("snapshot_name"),
        "training_stage": master.get("stage"),
        "source_continuous_manifest_sha256": master_sha,
        "snapshot_manifest_sha256": snapshot_manifest_sha,
        "runtime_manifest_sha256": runtime_manifest_sha,
        "runtime_index_sha256": _sha256(runtime_index_path),
        "live_formula_sha256": _sha256(snapshot_dir / "DeepPot.txt") if (snapshot_dir / "DeepPot.txt").exists() else None,
        "total_infosets": total_infosets,
        "structurally_resolvable_infosets": total_infosets if total_index_metadata_mismatches == 0 else None,
        "unknown_supported_keys": 0 if total_index_metadata_mismatches == 0 else None,
        "action_bit_mismatches": total_action_bit_mismatches,
        "index_metadata_mismatches": total_index_metadata_mismatches,
        "ready_for_live_v5": bool(snapshot.get("ready_for_live_v5")),
        "live_adapter_contract": snapshot.get("live_adapter_contract"),
        "modes": modes,
        "proof_scope": (
            "Every continuous-task greedy bitset used by the snapshot is SHA-verified and compared "
            "byte-for-byte against the release runtime; all 1,755 canonical flop slots per N are "
            "checked against runtime index card codes and hole-state widths; all 635,675,248 exact "
            "infosets are accounted for. This verifies policy/runtime equivalence, not live scraping."
        ),
    }

    if out_path is not None:
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description="Verify a DeepPot continuous snapshot against its exact CFR source")
    ap.add_argument("--training-root", required=True)
    ap.add_argument("--snapshot-dir", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    result = verify_continuous_snapshot(
        training_root=args.training_root,
        snapshot_dir=args.snapshot_dir,
        out_path=args.out,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["stage"] != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
