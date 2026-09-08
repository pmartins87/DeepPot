from deeppot.deepkk_style_compact import bit_is_set, evaluate_policy_deepkk_style_compact
from deeppot.deepkk_style_evaluator import evaluate_policy_deepkk_style
from deeppot.multiway_response import parse_flop


def test_compact_audit_matches_row_audit_with_complete_policy():
    flop = parse_flop("Ah 7d 2c")
    from deeppot.exact_index import ExactFlopHoleIndex
    from deeppot.state_space import decision_scenario_count

    h = len(ExactFlopHoleIndex.build(flop))
    width = h * decision_scenario_count(2)
    policy = {key: (0.55, 0.45) for key in range(width)}

    rows, row_summary = evaluate_policy_deepkk_style(
        num_players=2,
        flop=flop,
        policy=policy,
        samples=30,
        min_effective_visits=0.0,
        seed=777,
        rake_pct=0.02,
        rake_cap=None,
    )
    compact = evaluate_policy_deepkk_style_compact(
        num_players=2,
        flop=flop,
        policy=policy,
        samples=30,
        min_effective_visits=0.0,
        seed=777,
        rake_pct=0.02,
        rake_cap=None,
    )

    assert compact.expected_infosets == width
    assert compact.summary["covered_infosets"] == row_summary["covered_infosets"]
    assert compact.summary["confident_best_action_infosets"] == row_summary["confident_best_action_infosets"]
    assert compact.summary["low_coverage_infosets"] == row_summary["low_coverage_infosets"]

    for key, row in enumerate(rows):
        assert bit_is_set(compact.final_stay_bits, key) == (row["final_action"] == "STAY")
        assert bit_is_set(compact.solver_stay_bits, key) == (row["solver_greedy_action"] == "STAY")
        assert bit_is_set(compact.confident_bits, key) == bool(row["best_action_confident"])
        assert bit_is_set(compact.low_coverage_bits, key) == bool(row["low_coverage"])
