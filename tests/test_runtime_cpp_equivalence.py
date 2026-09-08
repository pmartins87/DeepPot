from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from deeppot.cards import Card
from deeppot.exact_index import ExactFlopHoleIndex
from deeppot.runtime_contract import SCENARIO_COUNTS, encoded_action_code, scenario_dense_id_from_mask
from deeppot.runtime_package import (
    RuntimeFlopRecord,
    RuntimePackage,
    _flop_codes_from_cards,
    _write_runtime_index,
)


def _build_one_flop_package(root: Path):
    flop = (Card.parse("Ah"), Card.parse("7d"), Card.parse("2c"))
    hole = (Card.parse("Ks"), Card.parse("Qs"))
    exact = ExactFlopHoleIndex.build(flop)
    hole_id = exact.state_id(flop, hole)
    scenario = scenario_dense_id_from_mask(4, 1, 0)

    root.mkdir(parents=True)
    (root / "strategy").mkdir()
    _write_runtime_index(
        root / "deeppot_runtime_index.bin",
        [
            RuntimeFlopRecord(
                flop_index=123,
                card_codes=_flop_codes_from_cards(flop),
                hole_state_count=len(exact),
            )
        ],
    )

    for n in range(2, 9):
        bit_count = len(exact) * SCENARIO_COUNTS[n]
        data = bytearray((bit_count + 7) // 8)
        if n == 4:
            key = scenario * len(exact) + hole_id
            data[key >> 3] |= 1 << (key & 7)
        (root / "strategy" / f"N{n}_final.bits").write_bytes(data)
    return flop, hole, hole_id, scenario


def test_python_and_cpp_runtime_lookup_are_identical(tmp_path: Path) -> None:
    compiler = shutil.which("g++")
    if compiler is None:
        pytest.skip("g++ unavailable")

    package_root = tmp_path / "package"
    flop, hole, hole_id, scenario = _build_one_flop_package(package_root)

    py = RuntimePackage(package_root).query(
        num_players=4,
        actor_index=1,
        prior_stay_mask=0,
        flop=flop,
        hole=hole,
    )
    assert py.stay is True
    assert py.flop_index == 123
    assert py.exact_hole_state_id == hole_id
    assert py.scenario_dense_id == scenario
    assert py.encoded_action == encoded_action_code(4, scenario, stay=True)

    repo = Path(__file__).resolve().parents[1]
    main_cpp = tmp_path / "main.cpp"
    main_cpp.write_text(
        r'''#include <array>
#include <iostream>
#include <string>
#include "deeppot_runtime_core.h"

int main(int argc, char** argv) {
  if (argc != 2) return 10;
  deeppot_runtime::Strategy strategy;
  std::string error;
  if (!strategy.Load(argv[1], &error)) {
    std::cerr << error << "\n";
    return 11;
  }
  std::array<deeppot_runtime::Card, 3> flop = {{{14,2},{7,1},{2,0}}};
  std::array<deeppot_runtime::Card, 2> hole = {{{13,3},{12,3}}};
  deeppot_runtime::QueryResult result = strategy.Query(4, 1, 0, flop, hole);
  if (!result.ok) {
    std::cerr << result.error << "\n";
    return 12;
  }
  std::cout << result.EncodedAction() << " "
            << result.flop_index << " "
            << result.exact_hole_state_id << " "
            << result.scenario_dense_id << "\n";
  return 0;
}
''',
        encoding="utf-8",
    )
    exe = tmp_path / "runtime_test"
    subprocess.run(
        [
            compiler,
            "-std=c++11",
            "-O2",
            "-I",
            str(repo / "runtime"),
            str(repo / "runtime" / "deeppot_runtime_core.cpp"),
            str(main_cpp),
            "-o",
            str(exe),
        ],
        check=True,
    )
    completed = subprocess.run(
        [str(exe), str(package_root)],
        check=True,
        capture_output=True,
        text=True,
    )
    action, flop_index, cpp_hole_id, cpp_scenario = map(int, completed.stdout.split())
    assert action == py.encoded_action
    assert flop_index == py.flop_index
    assert cpp_hole_id == py.exact_hole_state_id
    assert cpp_scenario == py.scenario_dense_id
