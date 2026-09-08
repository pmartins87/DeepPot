from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .cards import Card, canonical_flop_key
from .exact_index import ExactFlopHoleIndex
from .runtime_contract import (
    SCENARIO_COUNTS,
    encoded_action_code,
    scenario_dense_id_from_mask,
)


RUNTIME_INDEX_MAGIC = b"DPOTIDX1"
RUNTIME_INDEX_VERSION = 1
_HEADER = struct.Struct("<8sII")
_FLOP_RECORD = struct.Struct("<H3BH")


@dataclass(frozen=True)
class RuntimeFlopRecord:
    flop_index: int
    card_codes: tuple[int, int, int]
    hole_state_count: int


@dataclass(frozen=True)
class RuntimeDecision:
    num_players: int
    actor_index: int
    scenario_dense_id: int
    flop_index: int
    exact_hole_state_id: int
    stay: bool
    encoded_action: int


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _card_code(card: Card) -> int:
    return (card.rank - 2) * 4 + card.suit


def _flop_codes_from_cards(flop: Sequence[Card]) -> tuple[int, int, int]:
    key = canonical_flop_key(flop)
    return tuple((rank - 2) * 4 + suit for rank, suit in key)  # type: ignore[return-value]


def _flop_codes_from_texts(texts: Sequence[str]) -> tuple[int, int, int]:
    if len(texts) != 3:
        raise ValueError("flop record must contain exactly three cards")
    return _flop_codes_from_cards(tuple(Card.parse(x) for x in texts))


def _write_runtime_index(path: Path, records: Sequence[RuntimeFlopRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.write(_HEADER.pack(RUNTIME_INDEX_MAGIC, RUNTIME_INDEX_VERSION, len(records)))
        for row in records:
            handle.write(
                _FLOP_RECORD.pack(
                    row.flop_index,
                    row.card_codes[0],
                    row.card_codes[1],
                    row.card_codes[2],
                    row.hole_state_count,
                )
            )


def load_runtime_index(path: str | Path) -> tuple[RuntimeFlopRecord, ...]:
    raw = Path(path).read_bytes()
    if len(raw) < _HEADER.size:
        raise ValueError("runtime index is truncated")
    magic, version, count = _HEADER.unpack_from(raw, 0)
    if magic != RUNTIME_INDEX_MAGIC:
        raise ValueError("invalid DeepPot runtime index magic")
    if version != RUNTIME_INDEX_VERSION:
        raise ValueError(f"unsupported DeepPot runtime index version: {version}")
    expected_size = _HEADER.size + count * _FLOP_RECORD.size
    if len(raw) != expected_size:
        raise ValueError(f"runtime index length mismatch: {len(raw)} != {expected_size}")
    rows: list[RuntimeFlopRecord] = []
    offset = _HEADER.size
    for _ in range(count):
        flop_index, c0, c1, c2, holes = _FLOP_RECORD.unpack_from(raw, offset)
        offset += _FLOP_RECORD.size
        rows.append(RuntimeFlopRecord(flop_index, (c0, c1, c2), holes))
    if len({x.flop_index for x in rows}) != len(rows):
        raise ValueError("duplicate flop_index in runtime index")
    if len({x.card_codes for x in rows}) != len(rows):
        raise ValueError("duplicate canonical flop in runtime index")
    return tuple(rows)


def _load_source_mode(run_root: Path, n: int) -> tuple[dict, Path]:
    index_path = run_root / f"N{n}" / "compiled" / f"N{n}_index.json"
    if not index_path.exists():
        raise FileNotFoundError(index_path)
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    final_meta = payload.get("files", {}).get("final")
    if not isinstance(final_meta, dict) or "file" not in final_meta:
        raise ValueError(f"N={n} index does not describe final bitset")
    final_path = index_path.parent / str(final_meta["file"])
    if not final_path.exists():
        raise FileNotFoundError(final_path)
    expected_sha = str(final_meta.get("sha256", ""))
    if expected_sha and _sha256(final_path) != expected_sha:
        raise ValueError(f"N={n} final bitset SHA256 mismatch")
    return payload, final_path


def build_runtime_package(
    run_dir: str | Path,
    out_dir: str | Path,
    *,
    require_complete: bool = True,
) -> dict:
    """Compile a completed mathematical run into the minimal live lookup package.

    Only the final action bitsets are copied into the live package. Solver,
    confidence and low-coverage vectors remain preserved in the mathematical run
    for audit, but the bot does not need them to choose FOLD/STAY.
    """

    run_root = Path(run_dir)
    out_root = Path(out_dir)
    strategy_dir = out_root / "strategy"
    strategy_dir.mkdir(parents=True, exist_ok=True)

    source_run_manifest = run_root / "RUN_MANIFEST.json"
    source_manifest_payload: dict = {}
    if source_run_manifest.exists():
        source_manifest_payload = json.loads(source_run_manifest.read_text(encoding="utf-8"))
        if require_complete and source_manifest_payload.get("stage") != "completed":
            raise ValueError("source RUN_MANIFEST.json is not completed")

    canonical_rows: list[RuntimeFlopRecord] | None = None
    mode_manifest: dict[str, dict] = {}

    for n in range(2, 9):
        payload, final_path = _load_source_mode(run_root, n)
        flops = payload.get("flops")
        if not isinstance(flops, list) or not flops:
            raise ValueError(f"N={n} index has no flop rows")
        if require_complete:
            if payload.get("complete_mode") is not True:
                raise ValueError(f"N={n} mode is not marked complete")
            if len(flops) != 1755:
                raise ValueError(f"N={n} requires 1755 flops, got {len(flops)}")
            if [int(x["flop_index"]) for x in flops] != list(range(1755)):
                raise ValueError(f"N={n} complete flop indices are not exactly 0..1754")

        rows = [
            RuntimeFlopRecord(
                flop_index=int(x["flop_index"]),
                card_codes=_flop_codes_from_texts(tuple(x["flop"])),
                hole_state_count=int(x["hole_state_count"]),
            )
            for x in flops
        ]
        if canonical_rows is None:
            canonical_rows = rows
        elif rows != canonical_rows:
            raise ValueError(f"N={n} flop/hole-state metadata differs from N=2")

        expected_bytes = sum(
            (row.hole_state_count * SCENARIO_COUNTS[n] + 7) // 8
            for row in rows
        )
        if final_path.stat().st_size != expected_bytes:
            raise ValueError(
                f"N={n} final bitset length mismatch: "
                f"{final_path.stat().st_size} != {expected_bytes}"
            )

        dest = strategy_dir / f"N{n}_final.bits"
        shutil.copyfile(final_path, dest)
        mode_manifest[str(n)] = {
            "scenarios": SCENARIO_COUNTS[n],
            "infosets": sum(row.hole_state_count * SCENARIO_COUNTS[n] for row in rows),
            "file": f"strategy/{dest.name}",
            "bytes": dest.stat().st_size,
            "sha256": _sha256(dest),
        }

    assert canonical_rows is not None
    index_path = out_root / "deeppot_runtime_index.bin"
    _write_runtime_index(index_path, canonical_rows)

    source_sha = _sha256(source_run_manifest) if source_run_manifest.exists() else None
    manifest = {
        "format": "DeepPot OpenHoldem lossless exact-state runtime package",
        "runtime_index_version": RUNTIME_INDEX_VERSION,
        "flops": len(canonical_rows),
        "complete": len(canonical_rows) == 1755,
        "strategic_card_abstraction": "none",
        "action_encoding": {
            "symbol": "dll$deeppot_action",
            "zero": "invalid_or_unknown_fail_closed",
            "positive": "STAY; magnitude is global scenario code 1..494",
            "negative": "FOLD; magnitude is global scenario code 1..494",
        },
        "index": {
            "file": index_path.name,
            "bytes": index_path.stat().st_size,
            "sha256": _sha256(index_path),
        },
        "modes": mode_manifest,
        "source_run_manifest_sha256": source_sha,
        "source_generator_sha256": source_manifest_payload.get("source_sha256"),
        "source_economy_profile": source_manifest_payload.get("economy_profile"),
        "source_seed": source_manifest_payload.get("seed"),
    }
    manifest_path = out_root / "deeppot_runtime_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


class RuntimePackage:
    """Python reference implementation of the exact live bit lookup contract."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.records = load_runtime_index(self.root / "deeppot_runtime_index.bin")
        self._slot_by_flop = {row.card_codes: i for i, row in enumerate(self.records)}
        self._bits: dict[int, bytes] = {}
        self._offsets: dict[int, tuple[int, ...]] = {}
        for n in range(2, 9):
            path = self.root / "strategy" / f"N{n}_final.bits"
            data = path.read_bytes()
            offsets: list[int] = []
            cursor = 0
            for row in self.records:
                offsets.append(cursor)
                cursor += (row.hole_state_count * SCENARIO_COUNTS[n] + 7) // 8
            if len(data) != cursor:
                raise ValueError(f"N={n} runtime bitset length mismatch")
            self._bits[n] = data
            self._offsets[n] = tuple(offsets)

    def query(
        self,
        *,
        num_players: int,
        actor_index: int,
        prior_stay_mask: int,
        flop: Sequence[Card],
        hole: Sequence[Card],
    ) -> RuntimeDecision:
        if len(flop) != 3 or len(hole) != 2:
            raise ValueError("runtime query requires 3 flop cards and 2 hole cards")
        if num_players not in SCENARIO_COUNTS:
            raise ValueError("num_players must be between 2 and 8")

        codes = _flop_codes_from_cards(flop)
        try:
            slot = self._slot_by_flop[codes]
        except KeyError as exc:
            raise ValueError("canonical flop is absent from runtime package") from exc
        row = self.records[slot]

        exact = ExactFlopHoleIndex.build(flop)
        if len(exact) != row.hole_state_count:
            raise AssertionError("runtime package hole-state count disagrees with exact index")
        hole_id = exact.state_id(flop, hole)
        scenario = scenario_dense_id_from_mask(num_players, actor_index, prior_stay_mask)
        key = scenario * row.hole_state_count + hole_id
        byte_index = self._offsets[num_players][slot] + (key >> 3)
        bit_mask = 1 << (key & 7)
        stay = bool(self._bits[num_players][byte_index] & bit_mask)
        return RuntimeDecision(
            num_players=num_players,
            actor_index=actor_index,
            scenario_dense_id=scenario,
            flop_index=row.flop_index,
            exact_hole_state_id=hole_id,
            stay=stay,
            encoded_action=encoded_action_code(num_players, scenario, stay=stay),
        )


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the minimal DeepPot OpenHoldem runtime package")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()
    manifest = build_runtime_package(args.run_dir, args.out_dir, require_complete=True)
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
