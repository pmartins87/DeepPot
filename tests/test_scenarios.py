import itertools

import pytest

from deeppot.game import Action
from deeppot.scenarios import scenario_dense_id


def test_dense_scenario_ids_are_contiguous() -> None:
    for n in range(2, 9):
        ids = set()
        for actor in range(n):
            for bits in itertools.product((Action.FOLD, Action.STAY), repeat=actor):
                if actor == n - 1 and all(a == Action.FOLD for a in bits):
                    continue
                ids.add(scenario_dense_id(n, actor, bits))
        assert ids == set(range((1 << n) - 2))


def test_btn_all_fold_history_is_terminal() -> None:
    with pytest.raises(ValueError):
        scenario_dense_id(4, 3, (Action.FOLD, Action.FOLD, Action.FOLD))
