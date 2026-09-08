from __future__ import annotations

import argparse
import json
from pathlib import Path


def read_bit(path: Path, offset_bytes: int, bit_index: int) -> int:
    byte_index = offset_bytes + (bit_index // 8)
    bit_in_byte = bit_index % 8
    with path.open("rb") as f:
        f.seek(byte_index)
        raw = f.read(1)
    if len(raw) != 1:
        raise RuntimeError(f"cannot read bit {bit_index} from {path}")
    return (raw[0] >> bit_in_byte) & 1


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Inspect one exact DeepPot compiled decision and its audit flags."
    )
    ap.add_argument("--root", type=Path, default=Path("runs/deepkk_parity_full"))
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--flop-index", type=int, required=True)
    ap.add_argument("--scenario-id", type=int, required=True)
    ap.add_argument("--hole-state-id", type=int, required=True)
    args = ap.parse_args()

    compiled = args.root / f"N{args.n}" / "compiled"
    index_path = compiled / f"N{args.n}_index.json"
    if not index_path.exists():
        raise SystemExit(f"index not found: {index_path}")

    index = json.loads(index_path.read_text(encoding="utf-8"))
    row = next((r for r in index["flops"] if int(r["flop_index"]) == args.flop_index), None)
    if row is None:
        raise SystemExit(f"flop_index {args.flop_index} not found in {index_path}")

    h = int(row["hole_state_count"])
    scenarios = int(row["public_scenarios"])
    if not 0 <= args.scenario_id < scenarios:
        raise SystemExit(f"scenario-id out of range: {args.scenario_id} / {scenarios}")
    if not 0 <= args.hole_state_id < h:
        raise SystemExit(f"hole-state-id out of range: {args.hole_state_id} / {h}")

    local_bit_key = args.scenario_id * h + args.hole_state_id
    values: dict[str, int] = {}
    for name in ("final", "solver", "confident", "low_coverage"):
        file_name = index["files"][name]["file"]
        offset = int(row["offset_bytes"][name])
        values[name] = read_bit(compiled / file_name, offset, local_bit_key)

    out = {
        "n": args.n,
        "flop_index": args.flop_index,
        "flop_id": row["flop_id"],
        "flop": row["flop"],
        "scenario_id": args.scenario_id,
        "hole_state_id": args.hole_state_id,
        "hole_state_count": h,
        "local_bit_key": local_bit_key,
        "final_action": "STAY" if values["final"] else "FOLD",
        "solver_action": "STAY" if values["solver"] else "FOLD",
        "confident": bool(values["confident"]),
        "low_coverage": bool(values["low_coverage"]),
        "ev_override_vs_solver": bool(values["confident"] and values["final"] != values["solver"]),
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
