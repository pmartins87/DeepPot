import json

from deeppot.deepkk_style_streaming import run_streaming_deepkk_parity


def test_streaming_deepkk_parity_one_flop_end_to_end_and_resume(tmp_path):
    out = tmp_path / "run"
    kwargs = dict(
        out_dir=out,
        players=(2,),
        iterations=20_000,
        audit_samples=30,
        min_effective_visits=0.0,
        seed=123,
        rake_pct=0.02,
        rake_cap=None,
        economy_profile="test-2pct",
        workers=1,
        start_index=0,
        limit=1,
    )

    first = run_streaming_deepkk_parity(**kwargs)
    assert first["stage"] == "completed"
    assert first["mode_results"]["2"]["flops"] == 1
    assert (out / "N2" / "compiled" / "N2_final.bits").exists()
    assert (out / "N2" / "compiled" / "N2_solver.bits").exists()
    assert (out / "N2" / "compiled" / "N2_confident.bits").exists()
    assert (out / "N2" / "compiled" / "N2_low_coverage.bits").exists()

    index = json.loads((out / "N2" / "compiled" / "N2_index.json").read_text())
    assert index["selection_flops"] == 1
    assert index["complete_mode"] is False
    assert index["flops"][0]["flop_index"] == 0

    # Same config/source must reuse the completed per-flop checkpoint cleanly.
    second = run_streaming_deepkk_parity(**kwargs)
    assert second["stage"] == "completed"
    assert second["mode_results"]["2"]["flops"] == 1
