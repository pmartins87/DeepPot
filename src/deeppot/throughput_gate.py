from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from pathlib import Path

from .benchmark import run_case

THROUGHPUT_GATE_VERSION = "2026-09-07.1"
FIXED_FLOP = "Ah 7d 2c"
FIXED_CASES = {
    2: 50_000,
    3: 20_000,
    4: 10_000,
    5: 5_000,
    6: 2_000,
    7: 1_000,
    8: 500,
}


def run_fixed_gate(*, seed: int, rake_pct: float, rake_cap: float | None) -> dict:
    cases = []
    for num_players in range(2, 9):
        cases.append(
            run_case(
                num_players=num_players,
                flop_text=FIXED_FLOP,
                iterations=FIXED_CASES[num_players],
                seed=seed,
                rake_pct=rake_pct,
                rake_cap=rake_cap,
            )
        )
    return {
        "throughput_gate_version": THROUGHPUT_GATE_VERSION,
        "generated_at_unix": time.time(),
        "python_version": sys.version,
        "platform": platform.platform(),
        "flop": FIXED_FLOP,
        "fixed_iterations_by_players": {str(k): v for k, v in FIXED_CASES.items()},
        "seed": seed,
        "rake_pct": rake_pct,
        "rake_cap": rake_cap,
        "strategic_card_abstraction": "none",
        "cases": cases,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="DeepPot finite N=2..8 throughput gate")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--rake-pct", type=float, default=0.02)
    ap.add_argument("--rake-cap", type=float, default=None)
    ap.add_argument("--out", default="throughput_gate.json")
    args = ap.parse_args()
    payload = run_fixed_gate(seed=args.seed, rake_pct=args.rake_pct, rake_cap=args.rake_cap)
    text = json.dumps(payload, indent=2)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
