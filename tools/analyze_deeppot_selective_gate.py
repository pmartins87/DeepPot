from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

from deeppot.cards import Card, canonical_flop_id, enumerate_canonical_flops
from deeppot.exact_index import ExactFlopHoleIndex
from deeppot.state_space import decision_scenario_count


POPCOUNT = bytes(bin(i).count("1") for i in range(256))


def popcount_bytes(data: bytes) -> int:
    return sum(POPCOUNT[b] for b in data)


def xor_count(a: bytes, b: bytes) -> int:
    if len(a) != len(b):
        raise RuntimeError(f"bitset length mismatch: {len(a)} != {len(b)}")
    return sum(POPCOUNT[x ^ y] for x, y in zip(a, b))


def cards_from_key(key):
    return tuple(Card(rank, suit) for rank, suit in key)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    pos = q * (len(xs) - 1)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return xs[lo]
    frac = pos - lo
    return xs[lo] * (1.0 - frac) + xs[hi] * frac


def main() -> None:
    ap = argparse.ArgumentParser(description="Analyze DeepPot snapshot stability per independent (N, canonical flop) CFR task")
    ap.add_argument("--training-root", default=r"C:\DeepPot\runs\continuous_master_fast_v2")
    ap.add_argument("--previous", default="V2_1500")
    ap.add_argument("--current", default="V2_2000")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    root = Path(args.training_root)
    prev_root = root / "snapshots" / args.previous / "DeepPotRuntime" / "strategy"
    cur_root = root / "snapshots" / args.current / "DeepPotRuntime" / "strategy"
    if not prev_root.exists():
        raise RuntimeError(f"previous snapshot strategy directory not found: {prev_root}")
    if not cur_root.exists():
        raise RuntimeError(f"current snapshot strategy directory not found: {cur_root}")

    out_dir = Path(args.out) if args.out else root / "analysis" / f"{args.previous}_to_{args.current}"
    out_dir.mkdir(parents=True, exist_ok=True)

    flops = enumerate_canonical_flops()
    hole_counts: list[int] = []
    flop_ids: list[str] = []
    print(f"Building exact flop boundaries for {len(flops):,} canonical flops...", flush=True)
    for key in flops:
        flop = cards_from_key(key)
        hole_counts.append(len(ExactFlopHoleIndex.build(flop)))
        flop_ids.append(canonical_flop_id(flop))

    rows: list[dict] = []
    total_changed = 0
    total_infosets = 0

    for n in range(2, 9):
        prev = (prev_root / f"N{n}_final.bits").read_bytes()
        cur = (cur_root / f"N{n}_final.bits").read_bytes()
        if len(prev) != len(cur):
            raise RuntimeError(f"N={n}: snapshot bitset byte lengths differ")

        offset = 0
        scenarios = decision_scenario_count(n)
        for flop_index, (flop_key, hole_count, flop_id) in enumerate(zip(flops, hole_counts, flop_ids)):
            infosets = scenarios * hole_count
            size = (infosets + 7) // 8
            a = prev[offset : offset + size]
            b = cur[offset : offset + size]
            if len(a) != size or len(b) != size:
                raise RuntimeError(f"N={n} flop={flop_index}: truncated mode bitset")
            changed = xor_count(a, b)
            changed_pct = 100.0 * changed / infosets

            summary_path = root / f"N{n}" / "summaries" / f"flop_{flop_index:04d}_{flop_id}.json"
            if not summary_path.exists():
                raise RuntimeError(f"missing current task summary: {summary_path}")
            s = read_json(summary_path)

            row = {
                "n": n,
                "flop_index": flop_index,
                "flop_id": flop_id,
                "hole_states": hole_count,
                "infosets": infosets,
                "changed_actions": changed,
                "changed_pct": changed_pct,
                "visit_min": int(s.get("visit_min", 0)),
                "visit_mean": float(s.get("visit_mean", 0.0)),
                "visit_median": int(s.get("visit_median", 0)),
                "iterations_completed": int(s.get("iterations_completed", 0)),
                "mixed_45_55_pct": float(s.get("average_policy_45_55_pct", 0.0)),
                "greedy_stay_pct": float(s.get("greedy_stay_pct", 0.0)),
            }
            rows.append(row)
            total_changed += changed
            total_infosets += infosets
            offset += size

        if offset != len(cur):
            raise RuntimeError(f"N={n}: expected to consume {offset} bytes, file has {len(cur)}")

    csv_path = out_dir / "task_stability.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    by_n = {}
    for n in range(2, 9):
        rr = [r for r in rows if r["n"] == n]
        changes = sum(r["changed_actions"] for r in rr)
        infosets = sum(r["infosets"] for r in rr)
        pcts = [r["changed_pct"] for r in rr]
        by_n[str(n)] = {
            "tasks": len(rr),
            "changed_actions": changes,
            "changed_pct_weighted": 100.0 * changes / infosets,
            "task_changed_pct_median": quantile(pcts, 0.50),
            "task_changed_pct_p90": quantile(pcts, 0.90),
            "task_changed_pct_p95": quantile(pcts, 0.95),
            "task_changed_pct_max": max(pcts),
        }

    threshold_summary = {}
    for threshold in (0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0):
        selected = [r for r in rows if r["changed_pct"] > threshold]
        selected_changes = sum(r["changed_actions"] for r in selected)
        selected_infosets = sum(r["infosets"] for r in selected)
        threshold_summary[str(threshold)] = {
            "tasks_above": len(selected),
            "tasks_above_pct": 100.0 * len(selected) / len(rows),
            "infosets_in_tasks_above": selected_infosets,
            "infosets_in_tasks_above_pct": 100.0 * selected_infosets / total_infosets,
            "share_of_all_changed_actions_pct": 100.0 * selected_changes / max(1, total_changed),
        }

    top = sorted(rows, key=lambda r: r["changed_pct"], reverse=True)[:30]
    payload = {
        "previous_snapshot": args.previous,
        "current_snapshot": args.current,
        "tasks": len(rows),
        "exact_infosets": total_infosets,
        "changed_actions": total_changed,
        "changed_pct": 100.0 * total_changed / total_infosets,
        "by_n": by_n,
        "thresholds": threshold_summary,
        "top_30_unstable_tasks": top,
        "csv": str(csv_path),
    }
    json_path = out_dir / "task_stability_summary.json"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    print("DeepPot per-task stability analysis")
    print(f"  snapshots: {args.previous} -> {args.current}")
    print(f"  tasks: {len(rows):,}")
    print(f"  changed actions: {total_changed:,} ({payload['changed_pct']:.6f}%)")
    print("")
    print("By N (weighted action change | task median | task p90 | task max):")
    for n in range(2, 9):
        x = by_n[str(n)]
        print(
            f"  N={n}: {x['changed_pct_weighted']:.4f}% | "
            f"{x['task_changed_pct_median']:.4f}% | {x['task_changed_pct_p90']:.4f}% | "
            f"{x['task_changed_pct_max']:.4f}%"
        )
    print("")
    print("Candidate selective thresholds (task changed_pct > threshold):")
    for threshold in (1.0, 1.5, 2.0, 2.5, 3.0):
        x = threshold_summary[str(threshold)]
        print(
            f"  >{threshold:.1f}%: tasks={x['tasks_above']:,} ({x['tasks_above_pct']:.2f}%), "
            f"infosets={x['infosets_in_tasks_above_pct']:.2f}%, "
            f"captures={x['share_of_all_changed_actions_pct']:.2f}% of changed actions"
        )
    print("")
    print("Top 15 unstable tasks:")
    for r in top[:15]:
        print(
            f"  N={r['n']} flop={r['flop_index']:04d} {r['flop_id']} "
            f"change={r['changed_pct']:.4f}% mixed45/55={r['mixed_45_55_pct']:.4f}% "
            f"visit_min={r['visit_min']}"
        )
    print(f"\nCSV:  {csv_path}")
    print(f"JSON: {json_path}")


if __name__ == "__main__":
    main()
