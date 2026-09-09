from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Callable, Iterable, Sequence

from .cards import Card, require_unique
from .runtime_contract import encoded_action_code, scenario_dense_id_from_mask


@dataclass(frozen=True)
class ScrapeSnapshot:
    """Minimal live public-state observation used by the recovery layer.

    Values are intentionally accepted as raw integers. Invalid chair/count
    values are evidence failures, not constructor errors, because the purpose of
    this module is to recover from imperfect scrapes.
    """

    nchairs: int
    dealerchair: int
    userchair: int
    playersdealtbits: int
    playersplayingbits: int
    foldbits2: int
    nplayersdealt: int


@dataclass(frozen=True)
class PublicStateCandidate:
    num_players: int
    actor_index: int
    prior_stay_mask: int
    scenario_dense_id: int
    global_scenario_code: int
    action_order: tuple[int, ...]
    cost: int
    reasons: tuple[str, ...]

    @property
    def public_key(self) -> tuple[int, int, int]:
        return (self.num_players, self.actor_index, self.prior_stay_mask)


@dataclass(frozen=True)
class ConsensusResult:
    stay: bool | None
    stay_weight: float
    fold_weight: float
    candidate_count: int
    min_cost: int | None


def _bit_count(value: int) -> int:
    return int(value).bit_count()


def _hamming(a: int, b: int, nchairs: int) -> int:
    mask = (1 << nchairs) - 1
    return ((int(a) ^ int(b)) & mask).bit_count()


def _valid_chair(chair: int, nchairs: int) -> bool:
    return 0 <= int(chair) < int(nchairs)


def _seat_mask(nchairs: int) -> int:
    return (1 << nchairs) - 1


def _legal_dealt_masks(nchairs: int, userchair: int) -> Iterable[int]:
    if not _valid_chair(userchair, nchairs):
        return ()
    hero_bit = 1 << userchair
    full = 1 << nchairs
    return (
        mask
        for mask in range(full)
        if (mask & hero_bit) and 2 <= _bit_count(mask) <= 8
    )


def _dealt_cost(
    mask: int,
    current: ScrapeSnapshot,
    history: Sequence[ScrapeSnapshot],
) -> tuple[int, tuple[str, ...]]:
    nchairs = current.nchairs
    reasons: list[str] = []

    current_mask = current.playersdealtbits & _seat_mask(nchairs)
    current_distance = _hamming(mask, current_mask, nchairs)
    cost = 4 * current_distance
    if current_distance:
        reasons.append(f"dealt_current_hamming={current_distance}")

    # Same-hand stable dealt history is allowed to beat a transient current
    # seat-mask change. Matching history still costs 1 so a coherent current
    # scrape remains the unique zero-cost path.
    historical_masks = [
        s.playersdealtbits & _seat_mask(nchairs)
        for s in history
        if s.nchairs == nchairs
        and _valid_chair(s.userchair, nchairs)
        and 2 <= _bit_count(s.playersdealtbits & _seat_mask(nchairs)) <= 8
        and (s.playersdealtbits & (1 << current.userchair))
    ]
    if historical_masks:
        history_distance = min(_hamming(mask, h, nchairs) for h in historical_masks)
        history_cost = 1 + 2 * history_distance
        if history_cost < cost:
            cost = history_cost
            reasons = [f"dealt_from_same_hand_history_hamming={history_distance}"]

    if 2 <= current.nplayersdealt <= 8:
        count_delta = abs(_bit_count(mask) - current.nplayersdealt)
        if count_delta:
            cost += 3 * count_delta
            reasons.append(f"nplayersdealt_delta={count_delta}")

    return cost, tuple(reasons)


def _dealer_cost(
    dealer: int,
    dealt_mask: int,
    current: ScrapeSnapshot,
    history: Sequence[ScrapeSnapshot],
) -> tuple[int, tuple[str, ...]]:
    if not (dealt_mask & (1 << dealer)):
        raise ValueError("dealer candidate must be in dealt mask")

    if dealer == current.dealerchair and _valid_chair(current.dealerchair, current.nchairs):
        return 0, ()

    for snapshot in reversed(history):
        if (
            snapshot.nchairs == current.nchairs
            and snapshot.dealerchair == dealer
            and _valid_chair(snapshot.dealerchair, current.nchairs)
        ):
            return 1, ("dealer_from_same_hand_history",)

    return 6, ("dealer_without_current_or_history_support",)


def _action_assignments(
    order: Sequence[int],
    actor_index: int,
    snapshot: ScrapeSnapshot,
) -> tuple[tuple[int, int, tuple[str, ...]], ...]:
    """Return `(stay_mask, cost, reasons)` for prior actors.

    Pot Fold is a one-decision game. A prior actor absent from both the current
    playing mask and foldbits2 is normally a vanished folded cardback, therefore
    FOLD with only a very small repair cost. A playing+folded contradiction is
    branched instead of hard-failing.
    """

    choices: list[tuple[tuple[int, int, str | None], ...]] = []
    per_actor: list[tuple[tuple[int, int, str | None], ...]] = []
    for i in range(actor_index):
        seat = order[i]
        bit = 1 << seat
        playing = bool(snapshot.playersplayingbits & bit)
        folded = bool(snapshot.foldbits2 & bit)
        if playing and not folded:
            per_actor.append(((1, 0, None),))
        elif folded and not playing:
            per_actor.append(((0, 0, None),))
        elif not playing and not folded:
            per_actor.append(((0, 1, f"infer_prior_fold_seat={seat}"),))
        else:
            # Contradictory current evidence. Preserve both possibilities and
            # let public-state proximity + policy consensus decide.
            per_actor.append(
                (
                    (0, 3, f"contradictory_playing_folded_seat={seat}:FOLD"),
                    (1, 3, f"contradictory_playing_folded_seat={seat}:STAY"),
                )
            )

    if not per_actor:
        return ((0, 0, ()),)

    out: list[tuple[int, int, tuple[str, ...]]] = []
    for assignment in product(*per_actor):
        stay_mask = 0
        cost = 0
        reasons: list[str] = []
        for i, (stay, item_cost, reason) in enumerate(assignment):
            if stay:
                stay_mask |= 1 << i
            cost += item_cost
            if reason:
                reasons.append(reason)
        out.append((stay_mask, cost, tuple(reasons)))
    return tuple(out)


def recover_public_state_candidates(
    current: ScrapeSnapshot,
    history: Sequence[ScrapeSnapshot] = (),
    *,
    max_candidates: int = 64,
) -> tuple[PublicStateCandidate, ...]:
    """Generate the closest legal public states from noisy live evidence.

    This reference implementation intentionally searches the complete legal
    dealt-mask/dealer space for up to ten chairs. That is at most 1024 masks and
    is useful as an executable specification for the optimized C++ adapter.
    """

    if not 2 <= current.nchairs <= 10:
        return ()
    if not _valid_chair(current.userchair, current.nchairs):
        return ()

    hero_bit = 1 << current.userchair
    playing = current.playersplayingbits & _seat_mask(current.nchairs)
    folded = current.foldbits2 & _seat_mask(current.nchairs)

    best_by_key: dict[tuple[int, int, int], PublicStateCandidate] = {}
    for dealt in _legal_dealt_masks(current.nchairs, current.userchair):
        n = _bit_count(dealt)
        dealt_cost, dealt_reasons = _dealt_cost(dealt, current, history)

        hero_cost = 0
        hero_reasons: list[str] = []
        if not (playing & hero_bit):
            hero_cost += 4
            hero_reasons.append("hero_missing_from_playing")
        if folded & hero_bit:
            hero_cost += 6
            hero_reasons.append("hero_present_in_foldbits2")

        for dealer in range(current.nchairs):
            if not (dealt & (1 << dealer)):
                continue
            dealer_cost, dealer_reasons = _dealer_cost(dealer, dealt, current, history)

            order = tuple(
                seat
                for step in range(1, current.nchairs + 1)
                for seat in ((dealer + step) % current.nchairs,)
                if dealt & (1 << seat)
            )
            if len(order) != n or order[-1] != dealer:
                continue
            try:
                actor = order.index(current.userchair)
            except ValueError:
                continue

            for stay_mask, action_cost, action_reasons in _action_assignments(order, actor, current):
                try:
                    dense = scenario_dense_id_from_mask(n, actor, stay_mask)
                except ValueError:
                    # E.g. BTN after all prior players folded: that is terminal,
                    # not a legal hero decision state.
                    continue
                global_code = encoded_action_code(n, dense, stay=True)
                cost = dealt_cost + dealer_cost + hero_cost + action_cost
                reasons = tuple(
                    dealt_reasons
                    + dealer_reasons
                    + tuple(hero_reasons)
                    + action_reasons
                )
                candidate = PublicStateCandidate(
                    num_players=n,
                    actor_index=actor,
                    prior_stay_mask=stay_mask,
                    scenario_dense_id=dense,
                    global_scenario_code=global_code,
                    action_order=order,
                    cost=cost,
                    reasons=reasons,
                )
                old = best_by_key.get(candidate.public_key)
                if old is None or (candidate.cost, candidate.action_order) < (
                    old.cost,
                    old.action_order,
                ):
                    best_by_key[candidate.public_key] = candidate

    ordered = sorted(
        best_by_key.values(),
        key=lambda c: (
            c.cost,
            c.num_players,
            c.actor_index,
            c.prior_stay_mask,
            c.action_order,
        ),
    )
    return tuple(ordered[: max(1, int(max_candidates))])


def weighted_policy_consensus(
    candidates: Sequence[PublicStateCandidate],
    query_stay: Callable[[PublicStateCandidate], bool],
    *,
    cost_window: int = 3,
    clear_threshold: float = 0.65,
) -> ConsensusResult:
    """Resolve nearby public states using the immutable strategy itself.

    The closest candidate receives weight 1. Every additional cost point halves
    weight. Candidates farther than `min_cost + cost_window` are ignored.
    """

    if not candidates:
        return ConsensusResult(None, 0.0, 0.0, 0, None)
    min_cost = min(c.cost for c in candidates)
    selected = [c for c in candidates if c.cost <= min_cost + cost_window]
    stay_weight = 0.0
    fold_weight = 0.0
    for candidate in selected:
        weight = 0.5 ** (candidate.cost - min_cost)
        if query_stay(candidate):
            stay_weight += weight
        else:
            fold_weight += weight
    total = stay_weight + fold_weight
    if total <= 0.0:
        return ConsensusResult(None, 0.0, 0.0, len(selected), min_cost)
    stay_share = stay_weight / total
    fold_share = fold_weight / total
    if stay_share >= clear_threshold:
        action: bool | None = True
    elif fold_share >= clear_threshold:
        action = False
    else:
        action = None
    return ConsensusResult(action, stay_share, fold_share, len(selected), min_cost)


def is_top_pair_or_better(flop: Sequence[Card], hole: Sequence[Card]) -> bool:
    """Emergency-only flop floor used after policy-backed recovery is exhausted.

    This is deliberately not a strategy abstraction. It only answers whether
    the exact five known cards make at least top pair (including overpair,
    two-pair, trips, straight, flush, full house or quads).
    """

    if len(flop) != 3 or len(hole) != 2:
        raise ValueError("requires exactly three flop cards and two hole cards")
    cards = tuple(flop) + tuple(hole)
    require_unique(cards)

    rank_counts: dict[int, int] = {}
    for card in cards:
        rank_counts[card.rank] = rank_counts.get(card.rank, 0) + 1
    pairs = sum(1 for count in rank_counts.values() if count >= 2)
    if any(count >= 3 for count in rank_counts.values()) or pairs >= 2:
        return True

    # Five known cards can already form a straight or flush on the flop.
    ranks = set(rank_counts)
    straight_ranks = set(ranks)
    if 14 in straight_ranks:
        straight_ranks.add(1)
    if any(all(r in straight_ranks for r in range(start, start + 5)) for start in range(1, 11)):
        return True
    if len({card.suit for card in cards}) == 1:
        return True

    top_board_rank = max(card.rank for card in flop)
    h0, h1 = hole
    if h0.rank == h1.rank and h0.rank > top_board_rank:
        return True  # overpair
    if h0.rank == top_board_rank or h1.rank == top_board_rank:
        return True  # top pair
    return False
