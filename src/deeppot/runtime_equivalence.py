from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .runtime_package import load_runtime_index

EXPECTED_TOTAL_INFOSETS = 635_675_248
EXPECTED_FLOPS = 1_755


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _xor_bit_mismatches(a: Path, b: Path) -> int:
    if a.stat().st_size != b.stat().st_size:
        raise ValueError(f"length mismatch: {a} ({a.stat().st_size}) != {b} ({b.stat().st_size})")
    mismatches = 0
    with a.open("rb") as fa, b.open("rb") as fb:
        while True:
            ca = fa.read(1024 * 1024)
            cb = fb.read(1024 * 1024)
            if not ca and not cb:
                break
            if len(ca) != len(cb):
                raise ValueError("stream length mismatch")
            mismatches += sum((x ^ y).bit_count() for x, y in zip(ca, cb))
    return mismatches


def verify_equivalence(run_dir: str | Path, runtime_dir: str | Path, out_path: str | Path | None = None) -> dict:
    run_root = Path(run_dir)
    runtime_root = Path(runtime_dir)

    run_manifest_path = run_root / "RUN_MANIFEST.json"
    runtime_manifest_path = runtime_root / "deeppot_runtime_manifest.json"
    if not run_manifest_path.exists() or not runtime_manifest_path.exists():
        raise FileNotFoundError("required run/runtime manifest missing")

    run_manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))
    runtime_manifest = json.loads(runtime_manifest_path.read_text(encoding="utf-8"))
    if run_manifest.get("stage") != "completed":
        raise ValueError("mathematical run is not completed")
    if runtime_manifest.get("complete") is not True:
        raise ValueError("runtime package is not complete")
    run_sha = _sha256(run_manifest_path)
    if runtime_manifest.get("source_run_manifest_sha256") != run_sha:
        raise ValueError("runtime package was not built from this exact completed RUN_MANIFEST")

    runtime_index = load_runtime_index(runtime_root / "deeppot_runtime_index.bin")
    if len(runtime_index) != EXPECTED_FLOPS:
        raise ValueError(f"runtime index has {len(runtime_index)} flops, expected {EXPECTED_FLOPS}")

    total_infosets = 0
    total_action_bit_mismatches = 0
    total_index_metadata_mismatches = 0
    mode_rows: list[dict] = []

    for n in range(2, 9):
        source_index_path = run_root / f"N{n}" / "compiled" / f"N{n}_index.json"
        source_index = json.loads(source_index_path.read_text(encoding="utf-8"))
        flops = source_index.get("flops")
        if not isinstance(flops, list) or len(flops) != EXPECTED_FLOPS:
            raise ValueError(f"N={n} source index does not have exactly {EXPECTED_FLOPS} flops")
        if source_index.get("complete_mode") is not True:
            raise ValueError(f"N={n} source mode is not complete")

        index_mismatches = 0
        infosets = 0
        expected_runtime_bytes = 0
        for slot, src in enumerate(flops):
            rr = runtime_index[slot]
            if int(src["flop_index"]) != rr.flop_index:
                index_mismatches += 1
            if int(src["hole_state_count"]) != rr.hole_state_count:
                index_mismatches += 1
            infosets += int(src["expected_infosets"])
            expected_runtime_bytes += int(src["vector_bytes"])

        source_final_meta = source_index.get("files", {}).get("final", {})
        source_final = source_index_path.parent / str(source_final_meta.get("file", ""))
        runtime_final = runtime_root / "strategy" / f"N{n}_final.bits"
        if not source_final.exists() or not runtime_final.exists():
            raise FileNotFoundError(f"N={n} source/runtime final bitset missing")
        if source_final.stat().st_size != expected_runtime_bytes:
            raise ValueError(f"N={n} source final length differs from indexed vector bytes")
        if runtime_final.stat().st_size != expected_runtime_bytes:
            raise ValueError(f"N={n} runtime final length differs from indexed vector bytes")

        source_sha = _sha256(source_final)
        runtime_sha = _sha256(runtime_final)
        bit_mismatches = _xor_bit_mismatches(source_final, runtime_final)

        manifest_mode = runtime_manifest.get("modes", {}).get(str(n), {})
        if int(manifest_mode.get("infosets", -1)) != infosets:
            index_mismatches += 1
        if str(manifest_mode.get("sha256", "")) != runtime_sha:
            index_mismatches += 1

        mode_rows.append(
            {
                "N": n,
                "flops": EXPECTED_FLOPS,
                "infosets": infosets,
                "source_final_sha256": source_sha,
                "runtime_final_sha256": runtime_sha,
                "action_bit_mismatches": bit_mismatches,
                "index_metadata_mismatches": index_mismatches,
                "all_keys_structurally_resolvable": index_mismatches == 0,
            }
        )
        total_infosets += infosets
        total_action_bit_mismatches += bit_mismatches
        total_index_metadata_mismatches += index_mismatches

    if total_infosets != EXPECTED_TOTAL_INFOSETS:
        raise ValueError(f"unexpected total infosets: {total_infosets} != {EXPECTED_TOTAL_INFOSETS}")

    result = {
        "format": "DeepPot P7 mathematical-to-runtime exhaustive structural/bit equivalence",
        "stage": "PASS" if total_action_bit_mismatches == 0 and total_index_metadata_mismatches == 0 else "FAIL",
        "source_run_manifest_sha256": run_sha,
        "runtime_manifest_sha256": _sha256(runtime_manifest_path),
        "runtime_index_sha256": _sha256(runtime_root / "deeppot_runtime_index.bin"),
        "total_infosets": total_infosets,
        "structurally_resolvable_infosets": total_infosets if total_index_metadata_mismatches == 0 else None,
        "unknown_supported_keys": 0 if total_index_metadata_mismatches == 0 else None,
        "action_bit_mismatches": total_action_bit_mismatches,
        "index_metadata_mismatches": total_index_metadata_mismatches,
        "modes": mode_rows,
        "proof_scope": (
            "All 1,755 source flop records per N are matched to the runtime index; every per-flop "
            "hole-state width and infoset count is accounted for; source and runtime final action "
            "vectors are XOR-compared byte-for-byte. Exact card canonicalization/query implementation "
            "is separately regression-tested Python vs compiled C++."
        ),
    }

    if out_path is not None:
        path = Path(out_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description="Verify DeepPot P7 mathematical-to-runtime equivalence")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--runtime-dir", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    result = verify_equivalence(args.run_dir, args.runtime_dir, args.out)
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["stage"] != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
