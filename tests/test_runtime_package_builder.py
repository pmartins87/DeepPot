from __future__ import annotations

import hashlib
import json
from pathlib import Path

from deeppot.cards import Card
from deeppot.exact_index import ExactFlopHoleIndex
from deeppot.runtime_contract import SCENARIO_COUNTS, scenario_dense_id_from_mask
from deeppot.runtime_package import RuntimePackage, build_runtime_package, load_runtime_index


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_build_runtime_package_from_compiled_math_bitsets(tmp_path: Path) -> None:
    run = tmp_path / "run"
    out = tmp_path / "runtime"
    flop = (Card.parse("Ah"), Card.parse("7d"), Card.parse("2c"))
    hole = (Card.parse("Ks"), Card.parse("Qs"))
    exact = ExactFlopHoleIndex.build(flop)
    hole_id = exact.state_id(flop, hole)
    scenario = scenario_dense_id_from_mask(4, 1, 0)

    (run / "RUN_MANIFEST.json").parent.mkdir(parents=True, exist_ok=True)
    (run / "RUN_MANIFEST.json").write_text(
        json.dumps({"stage": "running", "source_sha256": "source", "seed": 123}),
        encoding="utf-8",
    )

    for n in range(2, 9):
        compiled = run / f"N{n}" / "compiled"
        compiled.mkdir(parents=True)
        expected = len(exact) * SCENARIO_COUNTS[n]
        data = bytearray((expected + 7) // 8)
        if n == 4:
            key = scenario * len(exact) + hole_id
            data[key >> 3] |= 1 << (key & 7)
        final = compiled / f"N{n}_final.bits"
        final.write_bytes(data)
        index = {
            "complete_mode": False,
            "flops": [
                {
                    "flop_index": 123,
                    "flop": ["Ah", "7d", "2c"],
                    "hole_state_count": len(exact),
                    "public_scenarios": SCENARIO_COUNTS[n],
                    "expected_infosets": expected,
                    "vector_bytes": len(data),
                }
            ],
            "files": {
                "final": {
                    "file": final.name,
                    "bytes": len(data),
                    "sha256": _sha(bytes(data)),
                }
            },
        }
        (compiled / f"N{n}_index.json").write_text(json.dumps(index), encoding="utf-8")

    manifest = build_runtime_package(run, out, require_complete=False)
    assert manifest["flops"] == 1
    assert manifest["complete"] is False
    assert set(manifest["modes"]) == {str(n) for n in range(2, 9)}
    assert len(load_runtime_index(out / "deeppot_runtime_index.bin")) == 1

    result = RuntimePackage(out).query(
        num_players=4,
        actor_index=1,
        prior_stay_mask=0,
        flop=flop,
        hole=hole,
    )
    assert result.stay is True
    assert result.flop_index == 123
    assert result.exact_hole_state_id == hole_id
