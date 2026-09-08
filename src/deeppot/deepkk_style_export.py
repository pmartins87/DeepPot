from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .game import Action
from .scenarios import actor_label, history_code, scenario_dense_id, scenario_id


@dataclass(frozen=True)
class ScenarioSpec:
    num_players: int
    dense_id: int
    actor_index: int
    actor: str
    prior_actions: tuple[Action, ...]
    scenario_name: str
    list_name: str


def enumerate_scenarios(num_players: int) -> tuple[ScenarioSpec, ...]:
    if not 2 <= num_players <= 8:
        raise ValueError("num_players must be between 2 and 8")
    out: list[ScenarioSpec] = []
    for actor in range(num_players):
        for bits in range(1 << actor):
            # All prior players folded before BTN -> hand already terminal.
            if actor == num_players - 1 and bits == 0:
                continue
            actions = tuple(
                Action.STAY if bits & (1 << i) else Action.FOLD
                for i in range(actor)
            )
            dense = scenario_dense_id(num_players, actor, actions)
            name = scenario_id(num_players, actor, actions)
            out.append(
                ScenarioSpec(
                    num_players=num_players,
                    dense_id=dense,
                    actor_index=actor,
                    actor=actor_label(num_players, actor),
                    prior_actions=actions,
                    scenario_name=name,
                    list_name=f"list_{name}_STAY",
                )
            )
    out.sort(key=lambda x: x.dense_id)
    expected = (1 << num_players) - 2
    if len(out) != expected:
        raise AssertionError(f"scenario catalogue mismatch N={num_players}: {len(out)} != {expected}")
    if [x.dense_id for x in out] != list(range(expected)):
        raise AssertionError("scenario dense IDs are not contiguous")
    return tuple(out)


def enumerate_all_scenarios() -> tuple[ScenarioSpec, ...]:
    return tuple(spec for n in range(2, 9) for spec in enumerate_scenarios(n))


def write_scenario_catalog_csv(path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "num_players",
            "scenario_dense_id",
            "actor_index",
            "actor",
            "prior_history",
            "scenario_name",
            "list_name",
        ])
        for spec in enumerate_all_scenarios():
            writer.writerow([
                spec.num_players,
                spec.dense_id,
                spec.actor_index,
                spec.actor,
                history_code(spec.prior_actions),
                spec.scenario_name,
                spec.list_name,
            ])


def exact_state_token(flop_index: int, exact_hole_state_id: int) -> str:
    if flop_index < 0 or exact_hole_state_id < 0:
        raise ValueError("state IDs must be non-negative")
    return f"F{flop_index:04d}_H{exact_hole_state_id:04d}"


def _load_stay_tokens(final_strategy_csv: str | Path) -> dict[tuple[int, int], list[str]]:
    out: dict[tuple[int, int], list[str]] = {}
    with Path(final_strategy_csv).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "num_players",
            "scenario_dense_id",
            "flop_index",
            "exact_hole_state_id",
            "final_action",
        }
        if not required.issubset(set(reader.fieldnames or ())):
            raise ValueError(f"final strategy CSV must contain {sorted(required)}")
        for row in reader:
            if row["final_action"].strip().upper() != "STAY":
                continue
            n = int(row["num_players"])
            sc = int(row["scenario_dense_id"])
            token = exact_state_token(int(row["flop_index"]), int(row["exact_hole_state_id"]))
            out.setdefault((n, sc), []).append(token)
    for tokens in out.values():
        tokens.sort()
    return out


def _wrap_tokens(tokens: Iterable[str], *, per_line: int = 10) -> str:
    values = list(tokens)
    if not values:
        return "// none"
    return "\n".join(" ".join(values[i : i + per_line]) for i in range(0, len(values), per_line))


def generate_deeppot_txt(final_strategy_csv: str | Path) -> str:
    """Create the immutable mathematical DeepPot source in DeepKK-like layout.

    Native OpenPPL handlists cannot encode the full flop-relative exact state,
    so these mathematical list entries are stable `F####_H####` tokens. The
    operational layer compiles the same lists into an exact lookup table/DLL.
    """

    stay = _load_stay_tokens(final_strategy_csv)
    scenarios = enumerate_all_scenarios()
    blocks: list[str] = [
        "##notes##",
        "// ============================================================================",
        "// DEEPPOT MATHEMATICAL BASE — DeepKK-style generated strategy",
        "// ============================================================================",
        "// Binary strategic actions: FOLD or POT/STAY.",
        "// Exactly 494 public decision scenarios across N=2..8.",
        "// Each scenario has one STAY list; absence from the list means FOLD.",
        "// Entries are lossless exact-state tokens F####_H####.",
        "// This file is the immutable mathematical source. The operational OpenHoldem",
        "// layer compiles these lists to an exact runtime lookup, analogous to the",
        "// DeepKK mathematical/operational separation.",
        "// ============================================================================",
        "",
    ]

    for n in range(2, 9):
        mode_specs = [x for x in scenarios if x.num_players == n]
        blocks.extend([
            "////////////////////////////////////////////////////////////////////////",
            f"// N={n} — {len(mode_specs)} strategic scenarios",
            "////////////////////////////////////////////////////////////////////////",
            "",
        ])
        for spec in mode_specs:
            blocks.append(f"// s{spec.dense_id:03d} actor={spec.actor} history={history_code(spec.prior_actions)}")
            blocks.append(f"##{spec.list_name}##")
            blocks.append(_wrap_tokens(stay.get((n, spec.dense_id), ())))
            blocks.append("")

    return "\n".join(blocks).rstrip() + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description="DeepKK-style DeepPot mathematical TXT exporter")
    ap.add_argument("--final-strategy", required=True)
    ap.add_argument("--out-txt", required=True)
    ap.add_argument("--out-scenarios", default=None)
    args = ap.parse_args()

    text = generate_deeppot_txt(args.final_strategy)
    out = Path(args.out_txt)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    if args.out_scenarios:
        write_scenario_catalog_csv(args.out_scenarios)


if __name__ == "__main__":
    main()
