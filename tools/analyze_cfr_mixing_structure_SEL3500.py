from __future__ import annotations

import argparse
import json
import math
import struct
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

from deeppot import continuous_training_fast_v2 as ct
from deeppot.continuous_runner_fast_v2 import production_source_sha256
from deeppot.state_space import decision_scenario_count


# Fine enough to distinguish near-pure residual mass from genuinely mixed regions.
EDGES = np.array(
    [
        0.0,
        0.01,
        0.05,
        0.10,
        0.20,
        0.30,
        0.40,
        0.45,
        0.50,
        0.55,
        0.60,
        0.70,
        0.80,
        0.90,
        0.95,
        0.99,
        1.0000000001,
    ],
    dtype=np.float64,
)

LABELS = [
    "[0,.01)",
    "[.01,.05)",
    "[.05,.10)",
    "[.10,.20)",
    "[.20,.30)",
    "[.30,.40)",
    "[.40,.45)",
    "[.45,.50)",
    "[.50,.55)",
    "[.55,.60)",
    "[.60,.70)",
    "[.70,.80)",
    "[.80,.90)",
    "[.90,.95)",
    "[.95,.99)",
    "[.99,1]",
]


class Agg:
    def __init__(self) -> None:
        self.total = 0
        self.visit_total = 0
        self.avg_hist = np.zeros(len(LABELS), dtype=np.int64)
        self.cur_hist = np.zeros(len(LABELS), dtype=np.int64)
        self.avg_hist_visit = np.zeros(len(LABELS), dtype=np.float64)
        self.cur_hist_visit = np.zeros(len(LABELS), dtype=np.float64)
        self.avg_near_45_55 = 0
        self.avg_mixed_40_60 = 0
        self.avg_mixed_30_70 = 0
        self.avg_mixed_10_90 = 0
        self.avg_near_pure_01_99 = 0
        self.cur_near_45_55 = 0
        self.cur_mixed_40_60 = 0
        self.cur_mixed_30_70 = 0
        self.cur_mixed_10_90 = 0
        self.cur_near_pure_01_99 = 0
        self.greedy_disagree = 0
        self.avg_mixed_current_same_pure = 0
        self.avg_mixed_current_opposite_pure = 0
        self.avg_mixed_current_still_mixed = 0
        self.avg_70_30_band = 0
        self.avg_70_30_current_same_pure = 0
        self.avg_70_30_current_opposite_pure = 0
        self.avg_70_30_current_still_mixed = 0

    def add(self, avg: np.ndarray, cur: np.ndarray, visits: np.ndarray) -> None:
        if avg.size == 0:
            return
        self.total += int(avg.size)
        self.visit_total += int(visits.sum(dtype=np.uint64))

        h, _ = np.histogram(avg, bins=EDGES)
        hc, _ = np.histogram(cur, bins=EDGES)
        self.avg_hist += h.astype(np.int64)
        self.cur_hist += hc.astype(np.int64)

        # Training-visit weighted views are diagnostic only; visits are not live reach.
        hv, _ = np.histogram(avg, bins=EDGES, weights=visits.astype(np.float64, copy=False))
        hcv, _ = np.histogram(cur, bins=EDGES, weights=visits.astype(np.float64, copy=False))
        self.avg_hist_visit += hv
        self.cur_hist_visit += hcv

        self.avg_near_45_55 += int(np.count_nonzero((avg >= 0.45) & (avg <= 0.55)))
        self.avg_mixed_40_60 += int(np.count_nonzero((avg >= 0.40) & (avg <= 0.60)))
        self.avg_mixed_30_70 += int(np.count_nonzero((avg >= 0.30) & (avg <= 0.70)))
        self.avg_mixed_10_90 += int(np.count_nonzero((avg >= 0.10) & (avg <= 0.90)))
        self.avg_near_pure_01_99 += int(np.count_nonzero((avg <= 0.01) | (avg >= 0.99)))

        self.cur_near_45_55 += int(np.count_nonzero((cur >= 0.45) & (cur <= 0.55)))
        self.cur_mixed_40_60 += int(np.count_nonzero((cur >= 0.40) & (cur <= 0.60)))
        self.cur_mixed_30_70 += int(np.count_nonzero((cur >= 0.30) & (cur <= 0.70)))
        self.cur_mixed_10_90 += int(np.count_nonzero((cur >= 0.10) & (cur <= 0.90)))
        self.cur_near_pure_01_99 += int(np.count_nonzero((cur <= 0.01) | (cur >= 0.99)))

        avg_g = avg >= 0.5
        cur_g = cur >= 0.5
        self.greedy_disagree += int(np.count_nonzero(avg_g != cur_g))

        # Is an average-policy mixture merely historical residue?  For every average
        # state in [10%,90%], classify the *current regret-matching* policy as pure
        # to the same majority, pure to the opposite side, or still mixed.
        mixed = (avg >= 0.10) & (avg <= 0.90)
        cur_stay_pure = cur >= 0.99
        cur_fold_pure = cur <= 0.01
        same = mixed & ((avg_g & cur_stay_pure) | ((~avg_g) & cur_fold_pure))
        opp = mixed & ((avg_g & cur_fold_pure) | ((~avg_g) & cur_stay_pure))
        still = mixed & (~cur_stay_pure) & (~cur_fold_pure)
        self.avg_mixed_current_same_pure += int(np.count_nonzero(same))
        self.avg_mixed_current_opposite_pure += int(np.count_nonzero(opp))
        self.avg_mixed_current_still_mixed += int(np.count_nonzero(still))

        # Around a 70/30 split in either direction: 65/35 through 75/25.
        band = ((avg >= 0.65) & (avg <= 0.75)) | ((avg >= 0.25) & (avg <= 0.35))
        same70 = band & ((avg_g & cur_stay_pure) | ((~avg_g) & cur_fold_pure))
        opp70 = band & ((avg_g & cur_fold_pure) | ((~avg_g) & cur_stay_pure))
        still70 = band & (~cur_stay_pure) & (~cur_fold_pure)
        self.avg_70_30_band += int(np.count_nonzero(band))
        self.avg_70_30_current_same_pure += int(np.count_nonzero(same70))
        self.avg_70_30_current_opposite_pure += int(np.count_nonzero(opp70))
        self.avg_70_30_current_still_mixed += int(np.count_nonzero(still70))

    def payload(self) -> dict:
        total = max(1, self.total)
        vt = max(1.0, float(self.visit_total))

        def pct(x: int) -> float:
            return 100.0 * x / total

        def subpct(x: int, den: int) -> float:
            return 100.0 * x / max(1, den)

        return {
            "infosets": self.total,
            "training_visits": self.visit_total,
            "average_policy_histogram": [
                {
                    "bin": LABELS[i],
                    "count": int(self.avg_hist[i]),
                    "pct": 100.0 * float(self.avg_hist[i]) / total,
                    "training_visit_weighted_pct": 100.0 * float(self.avg_hist_visit[i]) / vt,
                }
                for i in range(len(LABELS))
            ],
            "current_regret_matching_histogram": [
                {
                    "bin": LABELS[i],
                    "count": int(self.cur_hist[i]),
                    "pct": 100.0 * float(self.cur_hist[i]) / total,
                    "training_visit_weighted_pct": 100.0 * float(self.cur_hist_visit[i]) / vt,
                }
                for i in range(len(LABELS))
            ],
            "average_policy": {
                "near_45_55": self.avg_near_45_55,
                "near_45_55_pct": pct(self.avg_near_45_55),
                "mixed_40_60": self.avg_mixed_40_60,
                "mixed_40_60_pct": pct(self.avg_mixed_40_60),
                "mixed_30_70": self.avg_mixed_30_70,
                "mixed_30_70_pct": pct(self.avg_mixed_30_70),
                "mixed_10_90": self.avg_mixed_10_90,
                "mixed_10_90_pct": pct(self.avg_mixed_10_90),
                "near_pure_01_99": self.avg_near_pure_01_99,
                "near_pure_01_99_pct": pct(self.avg_near_pure_01_99),
            },
            "current_regret_matching_policy": {
                "near_45_55": self.cur_near_45_55,
                "near_45_55_pct": pct(self.cur_near_45_55),
                "mixed_40_60": self.cur_mixed_40_60,
                "mixed_40_60_pct": pct(self.cur_mixed_40_60),
                "mixed_30_70": self.cur_mixed_30_70,
                "mixed_30_70_pct": pct(self.cur_mixed_30_70),
                "mixed_10_90": self.cur_mixed_10_90,
                "mixed_10_90_pct": pct(self.cur_mixed_10_90),
                "near_pure_01_99": self.cur_near_pure_01_99,
                "near_pure_01_99_pct": pct(self.cur_near_pure_01_99),
            },
            "average_vs_current": {
                "greedy_side_disagreements": self.greedy_disagree,
                "greedy_side_disagreement_pct": pct(self.greedy_disagree),
                "average_mixed_10_90_count": self.avg_mixed_10_90,
                "average_mixed_now_pure_same_majority": self.avg_mixed_current_same_pure,
                "average_mixed_now_pure_same_majority_pct_of_avg_mixed": subpct(
                    self.avg_mixed_current_same_pure, self.avg_mixed_10_90
                ),
                "average_mixed_now_pure_opposite": self.avg_mixed_current_opposite_pure,
                "average_mixed_now_pure_opposite_pct_of_avg_mixed": subpct(
                    self.avg_mixed_current_opposite_pure, self.avg_mixed_10_90
                ),
                "average_mixed_now_still_mixed": self.avg_mixed_current_still_mixed,
                "average_mixed_now_still_mixed_pct_of_avg_mixed": subpct(
                    self.avg_mixed_current_still_mixed, self.avg_mixed_10_90
                ),
                "average_roughly_70_30_count": self.avg_70_30_band,
                "roughly_70_30_now_pure_same_majority": self.avg_70_30_current_same_pure,
                "roughly_70_30_now_pure_same_majority_pct": subpct(
                    self.avg_70_30_current_same_pure, self.avg_70_30_band
                ),
                "roughly_70_30_now_pure_opposite": self.avg_70_30_current_opposite_pure,
                "roughly_70_30_now_pure_opposite_pct": subpct(
                    self.avg_70_30_current_opposite_pure, self.avg_70_30_band
                ),
                "roughly_70_30_now_still_mixed": self.avg_70_30_current_still_mixed,
                "roughly_70_30_now_still_mixed_pct": subpct(
                    self.avg_70_30_current_still_mixed, self.avg_70_30_band
                ),
            },
        }


def _actor_ranges(n: int) -> list[tuple[int, int, int]]:
    """Return (actor, public_id_start, public_id_end_exclusive)."""
    out = []
    for actor in range(n):
        start = (1 << actor) - 1
        count = (1 << actor) if actor < n - 1 else (1 << actor) - 1
        out.append((actor, start, start + count))
    assert out[-1][2] == decision_scenario_count(n)
    return out


def _read_state_arrays(path: Path, expected_source_sha: str) -> tuple[dict, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    with path.open("rb") as f:
        magic = f.read(len(ct.STATE_MAGIC))
        if magic != ct.STATE_MAGIC:
            raise RuntimeError(f"invalid state magic: {path}")
        raw_len = f.read(4)
        if len(raw_len) != 4:
            raise RuntimeError(f"truncated state header length: {path}")
        hlen = struct.unpack("<I", raw_len)[0]
        header = json.loads(f.read(hlen).decode("utf-8"))
        if header.get("source_sha256") != expected_source_sha:
            raise RuntimeError(
                f"source provenance mismatch in {path}: {header.get('source_sha256')} != {expected_source_sha}"
            )
        expected = int(header["expected_infosets"])
        arrays = []
        for dtype in ("<f8", "<f8", "<f8", "<f8", "<u4"):
            a = np.fromfile(f, dtype=dtype, count=expected)
            if a.size != expected:
                raise RuntimeError(f"truncated state array in {path}")
            arrays.append(a)
        if f.read(1):
            raise RuntimeError(f"unexpected trailing bytes in {path}")
    return header, arrays[0], arrays[1], arrays[2], arrays[3], arrays[4]


def _probabilities(
    regret_fold: np.ndarray,
    regret_stay: np.ndarray,
    sum_fold: np.ndarray,
    sum_stay: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    denom_avg = sum_fold + sum_stay
    avg = np.divide(
        sum_stay,
        denom_avg,
        out=np.full(sum_stay.shape, 0.5, dtype=np.float64),
        where=denom_avg > 0.0,
    )
    rf = np.maximum(regret_fold, 0.0)
    rs = np.maximum(regret_stay, 0.0)
    denom_cur = rf + rs
    cur = np.divide(
        rs,
        denom_cur,
        out=np.full(rs.shape, 0.5, dtype=np.float64),
        where=denom_cur > 0.0,
    )
    # Guard tiny numerical overshoots.
    np.clip(avg, 0.0, 1.0, out=avg)
    np.clip(cur, 0.0, 1.0, out=cur)
    return avg, cur


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Read-only full-state audit of SEL3500 average-CFR mixing versus current regret-matching policy"
    )
    ap.add_argument("--training-root", default=r"C:\DeepPot\runs\continuous_master_fast_v2")
    ap.add_argument("--out", default="")
    ap.add_argument("--progress-every", type=int, default=250)
    args = ap.parse_args()

    root = Path(args.training_root).resolve()
    source_sha = production_source_sha256()
    tasks = ct._all_tasks()

    aggs: dict[str, Agg] = defaultdict(Agg)
    started = time.perf_counter()
    bytes_read = 0

    print("DeepPot SEL3500 CFR mixing-structure audit")
    print(f"  tasks: {len(tasks):,}")
    print("  reads persisted CFR state directly; no state/RNG/snapshot is modified")
    print("  average policy = cumulative linear-average CFR policy")
    print("  current policy = current regret-matching policy from final regrets")
    print("  purpose: distinguish structural mixing from historical averaging residue")
    print("  training-visit weighted percentages are diagnostic only, not live reach")

    for i, task in enumerate(tasks, 1):
        spath = ct.state_path(root, task)
        if not spath.exists():
            raise RuntimeError(f"missing state: {spath}")
        header, rf, rs, sf, ss, visits = _read_state_arrays(spath, source_sha)
        bytes_read += spath.stat().st_size
        h = int(header["hole_state_count"])
        scenarios = int(header["public_scenarios"])
        expected = int(header["expected_infosets"])
        if expected != scenarios * h:
            raise RuntimeError(f"invalid layout in {spath}")

        avg, cur = _probabilities(rf, rs, sf, ss)
        aggs["global"].add(avg, cur, visits)
        aggs[f"N{task.n}"].add(avg, cur, visits)

        # Scenario IDs for each actor are contiguous, so actor slices are exact and cheap.
        for actor, s0, s1 in _actor_ranges(task.n):
            a = s0 * h
            b = s1 * h
            key = f"N{task.n}_actor{actor}"
            aggs[key].add(avg[a:b], cur[a:b], visits[a:b])
            aggs["BTN_last" if actor == task.n - 1 else "non_BTN_earlier"].add(
                avg[a:b], cur[a:b], visits[a:b]
            )

        if args.progress_every > 0 and (i % args.progress_every == 0 or i == len(tasks)):
            elapsed = time.perf_counter() - started
            gib = bytes_read / (1024 ** 3)
            rate = gib / max(elapsed, 1e-9)
            print(
                f"  progress {i:,}/{len(tasks):,} | read={gib:.2f} GiB | "
                f"elapsed={elapsed/60:.1f} min | rate={rate:.3f} GiB/s",
                flush=True,
            )

    payload = {
        "format": "DeepPot SEL3500 CFR mixing structure audit",
        "training_root": str(root),
        "source_sha256": source_sha,
        "note": (
            "Current regret-matching policy is a diagnostic of where the solver is pointing now; "
            "it is not itself the production policy and does not by itself prove equilibrium mixing."
        ),
        "groups": {k: v.payload() for k, v in sorted(aggs.items())},
    }
    out = (
        Path(args.out)
        if args.out
        else root / "analysis" / "mixing_structure_SEL3500" / "mixing_structure.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    g = payload["groups"]["global"]
    a = g["average_policy"]
    c = g["current_regret_matching_policy"]
    x = g["average_vs_current"]
    print("\nGlobal summary:")
    print(f"  exact infosets: {g['infosets']:,}")
    print(
        f"  average CFR: near-pure <=1%/>=99% {a['near_pure_01_99_pct']:.3f}% | "
        f"mixed 10-90 {a['mixed_10_90_pct']:.3f}% | 30-70 {a['mixed_30_70_pct']:.3f}% | "
        f"40-60 {a['mixed_40_60_pct']:.3f}% | 45-55 {a['near_45_55_pct']:.3f}%"
    )
    print(
        f"  current RM:  near-pure <=1%/>=99% {c['near_pure_01_99_pct']:.3f}% | "
        f"mixed 10-90 {c['mixed_10_90_pct']:.3f}% | 30-70 {c['mixed_30_70_pct']:.3f}% | "
        f"40-60 {c['mixed_40_60_pct']:.3f}% | 45-55 {c['near_45_55_pct']:.3f}%"
    )
    print(
        f"  average-greedy vs current-greedy side disagreement: "
        f"{x['greedy_side_disagreements']:,} ({x['greedy_side_disagreement_pct']:.3f}%)"
    )
    print(
        f"  average mixed 10-90 -> current pure SAME majority: "
        f"{x['average_mixed_now_pure_same_majority_pct_of_avg_mixed']:.2f}% | "
        f"pure OPPOSITE: {x['average_mixed_now_pure_opposite_pct_of_avg_mixed']:.2f}% | "
        f"still mixed: {x['average_mixed_now_still_mixed_pct_of_avg_mixed']:.2f}%"
    )
    print(
        f"  roughly 70/30 average states: {x['average_roughly_70_30_count']:,} | "
        f"current pure SAME={x['roughly_70_30_now_pure_same_majority_pct']:.2f}% | "
        f"pure OPPOSITE={x['roughly_70_30_now_pure_opposite_pct']:.2f}% | "
        f"still mixed={x['roughly_70_30_now_still_mixed_pct']:.2f}%"
    )

    print("\nBy N (average CFR 10-90 mixed | current RM 10-90 mixed | greedy-side disagreement):")
    for n in range(2, 9):
        p = payload["groups"][f"N{n}"]
        print(
            f"  N={n}: {p['average_policy']['mixed_10_90_pct']:.3f}% | "
            f"{p['current_regret_matching_policy']['mixed_10_90_pct']:.3f}% | "
            f"{p['average_vs_current']['greedy_side_disagreement_pct']:.3f}%"
        )

    print("\nActor split:")
    for key, label in (("non_BTN_earlier", "earlier actors"), ("BTN_last", "BTN/last actor")):
        p = payload["groups"][key]
        print(
            f"  {label}: avg mixed10-90={p['average_policy']['mixed_10_90_pct']:.3f}% | "
            f"current mixed10-90={p['current_regret_matching_policy']['mixed_10_90_pct']:.3f}% | "
            f"avg45-55={p['average_policy']['near_45_55_pct']:.3f}% | "
            f"greedy disagreement={p['average_vs_current']['greedy_side_disagreement_pct']:.3f}%"
        )

    print(f"\nJSON: {out}")


if __name__ == "__main__":
    main()
