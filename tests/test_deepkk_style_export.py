import csv
from pathlib import Path

from deeppot.deepkk_style_export import (
    enumerate_all_scenarios,
    enumerate_scenarios,
    exact_state_token,
    generate_deeppot_txt,
)


def test_scenario_counts_match_full_nonterminal_public_tree():
    expected = {2: 2, 3: 6, 4: 14, 5: 30, 6: 62, 7: 126, 8: 254}
    for n, count in expected.items():
        specs = enumerate_scenarios(n)
        assert len(specs) == count
        assert [s.dense_id for s in specs] == list(range(count))
    assert len(enumerate_all_scenarios()) == 494


def test_exact_state_token_is_stable():
    assert exact_state_token(0, 0) == "F0000_H0000"
    assert exact_state_token(1754, 1175) == "F1754_H1175"


def test_txt_has_one_list_per_scenario_and_fold_default_semantics(tmp_path: Path):
    strategy = tmp_path / "strategy.csv"
    with strategy.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "num_players",
                "scenario_dense_id",
                "flop_index",
                "exact_hole_state_id",
                "final_action",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "num_players": 2,
                "scenario_dense_id": 0,
                "flop_index": 12,
                "exact_hole_state_id": 34,
                "final_action": "STAY",
            }
        )
        writer.writerow(
            {
                "num_players": 2,
                "scenario_dense_id": 1,
                "flop_index": 12,
                "exact_hole_state_id": 35,
                "final_action": "FOLD",
            }
        )

    text = generate_deeppot_txt(strategy)
    assert text.count("##list_") == 494
    assert "F0012_H0034" in text
    assert "F0012_H0035" not in text
    assert "absence from the list means FOLD" in text
