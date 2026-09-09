from deeppot.cards import Card
from deeppot.live_recovery import (
    ScrapeSnapshot,
    is_top_pair_or_better,
    recover_public_state_candidates,
    weighted_policy_consensus,
)


def _best(snapshot: ScrapeSnapshot, history=()):
    candidates = recover_public_state_candidates(snapshot, history)
    assert candidates
    return candidates[0]


def test_log_pf2_six_ambiguous_states_recover_to_legal_scenarios() -> None:
    cases = [
        # hole/flop are documented here only as human regression labels.
        ("7d5d/9s4cAs", ScrapeSnapshot(8, 5, 2, 247, 117, 128, 7), (7, 4, 5, 20, 135)),
        ("Qh4d/3d7cTc", ScrapeSnapshot(8, 3, 2, 255, 77, 176, 8), (8, 6, 20, 83, 324)),
        ("Ah8d/8h4dJs", ScrapeSnapshot(8, 5, 2, 255, 60, 193, 8), (8, 4, 0, 15, 256)),
        ("Th5c/Qs2s8s", ScrapeSnapshot(8, 2, 2, 255, 13, 240, 8), (8, 7, 33, 159, 400)),
        ("Tc7s/7d6h4d", ScrapeSnapshot(8, 4, 2, 255, 28, 224, 8), (8, 5, 0, 31, 272)),
        ("Ts9s/Th3sAd", ScrapeSnapshot(8, 5, 2, 255, 61, 192, 8), (8, 4, 4, 19, 260)),
    ]
    for label, snapshot, expected in cases:
        candidate = _best(snapshot)
        observed = (
            candidate.num_players,
            candidate.actor_index,
            candidate.prior_stay_mask,
            candidate.scenario_dense_id,
            candidate.global_scenario_code,
        )
        assert observed == expected, label
        assert candidate.cost >= 1  # the old runtime missed because foldbits2 was incomplete


def test_missing_current_btn_uses_same_hand_history() -> None:
    history = (
        ScrapeSnapshot(8, 4, 2, 255, 255, 0, 8),
    )
    current = ScrapeSnapshot(8, -1, 2, 255, 28, 224, 8)
    candidate = _best(current, history)
    assert candidate.num_players == 8
    assert candidate.actor_index == 5
    assert candidate.prior_stay_mask == 0
    assert candidate.global_scenario_code == 272
    assert "dealer_from_same_hand_history" in candidate.reasons


def test_mid_hand_extra_visible_seat_can_recover_stable_dealt_mask() -> None:
    # Stable hand began seven-handed with chair 3 empty. A new visible seat then
    # contaminates the current dealt scrape as if all eight seats belonged to the hand.
    history = (
        ScrapeSnapshot(8, 5, 2, 247, 247, 0, 7),
    )
    current = ScrapeSnapshot(8, 5, 2, 255, 117, 128, 7)
    candidate = _best(current, history)
    assert candidate.num_players == 7
    assert candidate.action_order == (6, 7, 0, 1, 2, 4, 5)
    assert any(reason.startswith("dealt_from_same_hand_history") for reason in candidate.reasons)


def test_playing_and_folded_contradiction_branches_instead_of_hard_miss() -> None:
    # Chair 5 is a prior actor and appears in both masks. Recovery must create
    # legal branches rather than returning no state.
    current = ScrapeSnapshot(
        nchairs=8,
        dealerchair=4,
        userchair=2,
        playersdealtbits=255,
        playersplayingbits=28 | (1 << 5),
        foldbits2=224 | (1 << 5),
        nplayersdealt=8,
    )
    candidates = recover_public_state_candidates(current)
    assert candidates
    nearest = [c for c in candidates if c.cost == candidates[0].cost]
    masks = {c.prior_stay_mask for c in nearest}
    assert 0 in masks
    assert 1 in masks


def test_policy_consensus_prefers_strategy_supported_nearby_action() -> None:
    current = ScrapeSnapshot(8, 4, 2, 255, 28, 224, 8)
    candidates = recover_public_state_candidates(current)
    assert candidates

    # Pretend every near candidate except a distant minority says STAY.
    min_cost = candidates[0].cost
    result = weighted_policy_consensus(
        candidates,
        lambda c: c.cost <= min_cost + 1,
        cost_window=3,
        clear_threshold=0.65,
    )
    assert result.stay is True
    assert result.stay_weight > result.fold_weight


def test_tc7_on_764_is_top_pair_emergency_floor() -> None:
    flop = tuple(Card.parse(x) for x in ("7d", "6h", "4d"))
    hole = tuple(Card.parse(x) for x in ("Tc", "7s"))
    assert is_top_pair_or_better(flop, hole)


def test_second_or_bottom_pair_is_not_mislabeled_as_top_pair() -> None:
    flop = tuple(Card.parse(x) for x in ("Th", "3s", "Ad"))
    hole = tuple(Card.parse(x) for x in ("Ts", "9s"))
    assert not is_top_pair_or_better(flop, hole)

    flop2 = tuple(Card.parse(x) for x in ("8h", "4d", "Js"))
    hole2 = tuple(Card.parse(x) for x in ("Ah", "8d"))
    assert not is_top_pair_or_better(flop2, hole2)
