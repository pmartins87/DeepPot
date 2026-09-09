from __future__ import annotations

import argparse
import json
from pathlib import Path

from deeppot.cards import Card
from deeppot.runtime_package import RuntimePackage


def _card(text: str) -> Card:
    return Card.parse(text)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Query one exact DeepPot live decision from raw hero/flop cards."
    )
    ap.add_argument("--root", type=Path, default=Path("runs/deeppot_runtime"))
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--actor", type=int, required=True)
    ap.add_argument(
        "--prior-stay-mask",
        type=lambda x: int(x, 0),
        required=True,
        help="Prior STAY bit mask; accepts decimal or 0x-prefixed hexadecimal.",
    )
    ap.add_argument("--flop", nargs=3, required=True, metavar=("C1", "C2", "C3"))
    ap.add_argument("--hole", nargs=2, required=True, metavar=("H1", "H2"))
    args = ap.parse_args()

    package = RuntimePackage(args.root)
    decision = package.query(
        num_players=args.n,
        actor_index=args.actor,
        prior_stay_mask=args.prior_stay_mask,
        flop=tuple(_card(x) for x in args.flop),
        hole=tuple(_card(x) for x in args.hole),
    )
    print(
        json.dumps(
            {
                "num_players": decision.num_players,
                "actor_index": decision.actor_index,
                "prior_stay_mask": args.prior_stay_mask,
                "scenario_dense_id": decision.scenario_dense_id,
                "flop_index": decision.flop_index,
                "exact_hole_state_id": decision.exact_hole_state_id,
                "action": "STAY" if decision.stay else "FOLD",
                "encoded_action": decision.encoded_action,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
