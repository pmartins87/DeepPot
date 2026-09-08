from __future__ import annotations

from dataclasses import dataclass


SCENARIO_COUNTS: dict[int, int] = {n: (1 << n) - 2 for n in range(2, 9)}
SCENARIO_OFFSETS: dict[int, int] = {}
_running = 0
for _n in range(2, 9):
    SCENARIO_OFFSETS[_n] = _running
    _running += SCENARIO_COUNTS[_n]
TOTAL_SCENARIOS = _running


@dataclass(frozen=True)
class DecodedActionCode:
    num_players: int
    scenario_dense_id: int
    global_scenario_id: int
    stay: bool


def scenario_dense_id_from_mask(
    num_players: int,
    actor_index: int,
    prior_stay_mask: int,
) -> int:
    """Runtime equivalent of ``scenarios.scenario_dense_id``.

    ``prior_stay_mask`` uses one bit per prior actor in action order:
    bit=0 means FOLD and bit=1 means STAY. The BTN all-prior-FOLD state is
    terminal and therefore intentionally has no decision scenario.
    """

    if not 2 <= num_players <= 8:
        raise ValueError("num_players must be between 2 and 8")
    if not 0 <= actor_index < num_players:
        raise ValueError("actor_index out of range")
    if prior_stay_mask < 0 or prior_stay_mask >= (1 << actor_index):
        raise ValueError("prior_stay_mask contains bits outside prior actors")

    offset = (1 << actor_index) - 1
    if actor_index == num_players - 1:
        if prior_stay_mask == 0:
            raise ValueError("BTN all-prior-FOLD history is terminal")
        return offset + prior_stay_mask - 1
    return offset + prior_stay_mask


def global_scenario_id(num_players: int, scenario_dense_id: int) -> int:
    if num_players not in SCENARIO_COUNTS:
        raise ValueError("num_players must be between 2 and 8")
    count = SCENARIO_COUNTS[num_players]
    if not 0 <= scenario_dense_id < count:
        raise ValueError("scenario_dense_id out of range")
    return SCENARIO_OFFSETS[num_players] + scenario_dense_id


def encoded_action_code(num_players: int, scenario_dense_id: int, *, stay: bool) -> int:
    """Encode scenario plus final action in the single OpenHoldem DLL result.

    OpenHoldem caches user-DLL evaluation per action orbit rather than per
    ``dll$`` symbol name. DeepPot therefore exposes one and only one live query,
    ``dll$deeppot_action``. Its magnitude identifies one of the 494 scenarios
    (1..494); its sign is the final action. Zero is reserved for invalid/unknown
    runtime state and must fail closed.
    """

    code = global_scenario_id(num_players, scenario_dense_id) + 1
    return code if stay else -code


def decode_action_code(code: int) -> DecodedActionCode:
    if code == 0:
        raise ValueError("zero is the invalid/fail-closed runtime code")
    magnitude = abs(int(code))
    if not 1 <= magnitude <= TOTAL_SCENARIOS:
        raise ValueError("runtime action code out of range")
    global_id = magnitude - 1
    for n in range(2, 9):
        start = SCENARIO_OFFSETS[n]
        count = SCENARIO_COUNTS[n]
        if start <= global_id < start + count:
            return DecodedActionCode(
                num_players=n,
                scenario_dense_id=global_id - start,
                global_scenario_id=global_id,
                stay=code > 0,
            )
    raise AssertionError("unreachable global scenario decode")
