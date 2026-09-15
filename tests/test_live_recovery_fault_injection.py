from __future__ import annotations

from deeppot.live_recovery import ScrapeSnapshot, recover_public_state_candidates
from deeppot.runtime_contract import scenario_dense_id_from_mask


def _snapshot(n: int, actor: int, stay_mask: int) -> ScrapeSnapshot:
    # Compact canonical seating: chairs 0..N-1 are dealt, BTN is N-1, so the
    # Pot-Fold action order is exactly 0..N-1 and userchair == actor.
    dealt = (1 << n) - 1
    playing = 0
    folded = 0
    for seat in range(n):
        if seat < actor:
            if stay_mask & (1 << seat):
                playing |= 1 << seat
            else:
                folded |= 1 << seat
        else:
            # Hero/future actors have not folded yet.
            playing |= 1 << seat
    return ScrapeSnapshot(
        nchairs=n,
        dealerchair=n - 1,
        userchair=actor,
        playersdealtbits=dealt,
        playersplayingbits=playing,
        foldbits2=folded,
        nplayersdealt=n,
    )


def _legal_states():
    for n in range(2, 9):
        for actor in range(n):
            for stay_mask in range(1 << actor):
                try:
                    scenario_dense_id_from_mask(n, actor, stay_mask)
                except ValueError:
                    continue
                yield n, actor, stay_mask


def _best_key(snapshot: ScrapeSnapshot, history=()):
    candidates = recover_public_state_candidates(snapshot, history)
    assert candidates
    c = candidates[0]
    return c.num_players, c.actor_index, c.prior_stay_mask


def test_all_494_legal_public_states_roundtrip_exactly() -> None:
    states = list(_legal_states())
    assert len(states) == 494
    for n, actor, stay_mask in states:
        assert _best_key(_snapshot(n, actor, stay_mask)) == (n, actor, stay_mask)


def test_missing_foldbit_never_changes_the_intended_public_state() -> None:
    # This is the exact live failure family seen in log_pf2: a prior folded
    # cardback disappears and foldbits2 loses the fold evidence.
    for n, actor, stay_mask in _legal_states():
        clean = _snapshot(n, actor, stay_mask)
        prior_folds = [
            seat
            for seat in range(actor)
            if not (stay_mask & (1 << seat))
        ]
        if not prior_folds:
            continue
        seat = prior_folds[0]
        noisy = ScrapeSnapshot(
            clean.nchairs,
            clean.dealerchair,
            clean.userchair,
            clean.playersdealtbits,
            clean.playersplayingbits,
            clean.foldbits2 & ~(1 << seat),
            clean.nplayersdealt,
        )
        assert _best_key(noisy, (clean,)) == (n, actor, stay_mask)


def test_one_frame_playingbit_drop_keeps_recent_stay_as_a_legal_near_candidate() -> None:
    # A transient scrape must not irreversibly reinterpret a prior STAY as a
    # FOLD. The clean same-hand observation is deliberately supplied as history.
    clean = _snapshot(8, 5, 0b00101)  # seats 0 and 2 stayed before Hero.
    seat = 2
    assert clean.playersplayingbits & (1 << seat)
    noisy = ScrapeSnapshot(
        clean.nchairs,
        clean.dealerchair,
        clean.userchair,
        clean.playersdealtbits,
        clean.playersplayingbits & ~(1 << seat),
        clean.foldbits2,
        clean.nplayersdealt,
    )
    candidates = recover_public_state_candidates(noisy, (clean,))
    keys = {c.public_key for c in candidates[:16]}
    assert (8, 5, 0b00101) in keys


def test_combined_btn_and_seatmask_noise_keeps_clean_state_nearby() -> None:
    # Same-hand history supplies the stable geometry while current scrape loses
    # BTN and invents an extra dealt chair.
    clean = ScrapeSnapshot(8, 5, 2, 247, 117, 128, 7)
    noisy = ScrapeSnapshot(8, -1, 2, 255, 117, 128, 8)
    candidates = recover_public_state_candidates(noisy, (clean,))
    keys = {c.public_key for c in candidates[:32]}
    assert (7, 4, 5) in keys
