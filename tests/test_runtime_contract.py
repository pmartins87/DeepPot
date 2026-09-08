import itertools

import pytest

from deeppot.game import Action
from deeppot.runtime_contract import (
    SCENARIO_COUNTS,
    SCENARIO_OFFSETS,
    TOTAL_SCENARIOS,
    decode_action_code,
    encoded_action_code,
    scenario_dense_id_from_mask,
)
from deeppot.scenarios import scenario_dense_id


def test_runtime_mask_mapping_matches_canonical_scenario_mapping() -> None:
    for n in range(2, 9):
        for actor in range(n):
            for mask in range(1 << actor):
                actions = tuple(
                    Action.STAY if mask & (1 << i) else Action.FOLD
                    for i in range(actor)
                )
                if actor == n - 1 and mask == 0:
                    with pytest.raises(ValueError):
                        scenario_dense_id_from_mask(n, actor, mask)
                    continue
                assert scenario_dense_id_from_mask(n, actor, mask) == scenario_dense_id(n, actor, actions)


def test_global_action_codes_are_exactly_signed_1_through_494() -> None:
    positive = []
    negative = []
    for n in range(2, 9):
        for dense in range(SCENARIO_COUNTS[n]):
            positive.append(encoded_action_code(n, dense, stay=True))
            negative.append(encoded_action_code(n, dense, stay=False))
    assert TOTAL_SCENARIOS == 494
    assert positive == list(range(1, 495))
    assert negative == list(range(-1, -495, -1))
    assert SCENARIO_OFFSETS == {2: 0, 3: 2, 4: 8, 5: 22, 6: 52, 7: 114, 8: 240}


def test_action_code_round_trip() -> None:
    for code in itertools.chain(range(1, 495), range(-1, -495, -1)):
        decoded = decode_action_code(code)
        assert encoded_action_code(
            decoded.num_players,
            decoded.scenario_dense_id,
            stay=decoded.stay,
        ) == code

    with pytest.raises(ValueError):
        decode_action_code(0)
    with pytest.raises(ValueError):
        decode_action_code(495)
