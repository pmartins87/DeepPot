from __future__ import annotations

import argparse
import csv
import statistics
from collections import defaultdict
from pathlib import Path

DEEPPOT_CANONICAL_FLOPS = 1755
DEEPPOT_ITERATIONS_PER_FLOP = 20_000
DEEPPOT_CARD_STATES_PER_PUBLIC_SCENARIO = 1_286_792
DEEPPOT_PUBLIC_SCENARIOS = 494
DEEPPOT_TOTAL_INFOSETS = 635_675_248
DEEPPOT_AUDIT_SAMPLES_PER_FLOP = 50_000
DEEPPOT_AUDIT_MIN_EFFECTIVE = 25


def mode_from_scenario(s: str) -> str:
    if s.endswith("_2w"):
        return "2w"
    if s.endswith("_3w"):
        return "3w"
    return "4w"


def summarize(values: list[int]) -> tuple[int, float, float, int, int]:
    return (
        sum(values),
        statistics.mean(values),
        statistics.median(values),
        min(values),
        max(values),
    )


def find_seed123_csvs(root: Path, filename: str) -> list[Path]:
    hits = [p for p in root.rglob(filename) if "solve_seed_123" in str(p)]
    if hits:
        return sorted(hits)
    return sorted(root.rglob(filename))


def read_solver_policy(paths: list[Path]) -> dict[tuple[str, str], list[int]]:
    out: dict[tuple[str, str], list[int]] = defaultdict(list)
    for p in paths:
        with p.open("r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                scenario = str(row["scenario"])
                mode = mode_from_scenario(scenario)
                out[(mode, scenario)].append(int(float(row["visit_count"])))
    return out


def read_ev_audit(paths: list[Path]) -> dict[tuple[str, str], dict[str, int]]:
    out: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: {
        "infosets": 0,
        "visits": 0,
        "min_visits": 10**30,
        "max_visits": 0,
        "confident": 0,
        "low": 0,
    })
    for p in paths:
        with p.open("r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                scenario = str(row["scenario"])
                mode = mode_from_scenario(scenario)
                k = (mode, scenario)
                d = out[k]
                v = int(float(row["visits"]))
                d["infosets"] += 1
                d["visits"] += v
                d["min_visits"] = min(d["min_visits"], v)
                d["max_visits"] = max(d["max_visits"], v)
                d["confident"] += int(float(row["best_action_confident"]))
                d["low"] += int(float(row["low_coverage"]))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Read-only DeepKK vs DeepPot training-volume comparison")
    ap.add_argument(
        "--deepkk-run",
        type=Path,
        default=Path(r"C:\aof_rb40_v4\RYZEN9\runs\20260717_210508_deepkk_oficial"),
    )
    args = ap.parse_args()

    root = args.deepkk_run
    if not root.exists():
        raise SystemExit(f"DeepKK canonical run not found: {root}")

    solver_paths = find_seed123_csvs(root, "solver_policy.csv")
    if not solver_paths:
        raise SystemExit(f"No solver_policy.csv found under: {root}")
    solver = read_solver_policy(solver_paths)

    ev_paths = find_seed123_csvs(root, "ev_best_action_table.csv")
    audit = read_ev_audit(ev_paths) if ev_paths else {}

    print("DEEPPOT — EXACT STRUCTURAL TRAINING VOLUME")
    per_scenario = DEEPPOT_CANONICAL_FLOPS * DEEPPOT_ITERATIONS_PER_FLOP
    avg_per_infoset = per_scenario / DEEPPOT_CARD_STATES_PER_PUBLIC_SCENARIO
    total_node_visits = per_scenario * DEEPPOT_PUBLIC_SCENARIOS
    total_chance_deals = DEEPPOT_CANONICAL_FLOPS * DEEPPOT_ITERATIONS_PER_FLOP * 7
    total_audit_deals = DEEPPOT_CANONICAL_FLOPS * DEEPPOT_AUDIT_SAMPLES_PER_FLOP * 7
    print(f"public scenarios: {DEEPPOT_PUBLIC_SCENARIOS:,}")
    print(f"exact infosets: {DEEPPOT_TOTAL_INFOSETS:,}")
    print(f"training node visits per public scenario across all flops: {per_scenario:,}")
    print(f"average training visits per exact infoset: {avg_per_infoset:,.6f}")
    print(f"total CFR node visits: {total_node_visits:,}")
    print(f"total sampled chance deals across N=2..8: {total_chance_deals:,}")
    print(f"audit sampled chance deals across N=2..8: {total_audit_deals:,}")
    print(f"audit threshold: effective visits >= {DEEPPOT_AUDIT_MIN_EFFECTIVE}")
    print()

    print("DEEPKK — ACTUAL SEED-123 TRAINING VISITS FROM solver_policy.csv")
    print(f"files read: {len(solver_paths)}")
    print("mode  scenario                                      total_visits      mean/hand    median/hand     min/hand     max/hand")
    print("----  --------------------------------------------  ---------------  ------------  ------------  -----------  -----------")
    for (mode, scenario), vals in sorted(solver.items(), key=lambda x: ({"4w":0,"3w":1,"2w":2}[x[0][0]], x[0][1])):
        total, mean, med, mn, mx = summarize(vals)
        print(f"{mode:4}  {scenario:44}  {total:15,d}  {mean:12,.1f}  {med:12,.1f}  {mn:11,d}  {mx:11,d}")

    total_deepkk_training_visits = sum(sum(v) for v in solver.values())
    deepkk_infosets = sum(len(v) for v in solver.values())
    print()
    print(f"DEEPKK total actual regret-node visits: {total_deepkk_training_visits:,}")
    print(f"DEEPKK infosets represented: {deepkk_infosets:,}")
    print(f"DEEPKK mean actual training visits / infoset: {total_deepkk_training_visits / deepkk_infosets:,.1f}")
    print(f"DeepPot/DeepKK infoset dimension ratio: {DEEPPOT_TOTAL_INFOSETS / deepkk_infosets:,.1f}x")
    print(f"DeepPot/DeepKK total regret-node-visit ratio: {total_node_visits / total_deepkk_training_visits:,.3f}x")
    print(f"DeepKK/DeepPot mean visits-per-infoset ratio: {(total_deepkk_training_visits / deepkk_infosets) / avg_per_infoset:,.1f}x")

    if audit:
        print()
        print("DEEPKK — ACTUAL EV AUDIT BY SCENARIO")
        print("mode  scenario                                      infosets  avg_visits  min_visits  max_visits  confident  low_cov")
        print("----  --------------------------------------------  --------  ----------  ----------  ----------  ---------  -------")
        for (mode, scenario), d in sorted(audit.items(), key=lambda x: ({"4w":0,"3w":1,"2w":2}[x[0][0]], x[0][1])):
            avg = d["visits"] / max(1, d["infosets"])
            print(
                f"{mode:4}  {scenario:44}  {d['infosets']:8,d}  {avg:10,.1f}  "
                f"{d['min_visits']:10,d}  {d['max_visits']:10,d}  {d['confident']:9,d}  {d['low']:7,d}"
            )
    else:
        print()
        print("No ev_best_action_table.csv found; DeepKK audit scenario details were not printed.")


if __name__ == "__main__":
    main()
