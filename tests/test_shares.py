"""Деление долей. Числа в первых трёх примерах сняты с видео работающего редактора."""

import pytest

from app.shares import rebalance, split_evenly


@pytest.mark.parametrize(
    ("total", "count", "expected"),
    [
        (100, 3, [33, 33, 34]),  # видео: три оффера в потоке
        (75, 2, [38, 37]),  # видео: 25 закреплено, двое делят остальное
        (100, 4, [25, 25, 25, 25]),  # видео: добавили четвёртый
        (100, 5, [20, 20, 20, 20, 20]),  # видео: добавили пятый
        (100, 1, [100]),
        (100, 2, [50, 50]),
        (100, 6, [17, 17, 17, 17, 17, 15]),
        (100, 7, [14, 14, 14, 14, 14, 14, 16]),
        (0, 3, [0, 0, 0]),
        (5, 8, [0, 0, 0, 0, 0, 0, 0, 5]),  # свободных процентов меньше, чем офферов
        (-10, 2, [0, 0]),  # закреплённые доли заняли больше 100
        (100, 0, []),
    ],
)
def test_split_evenly(total, count, expected):
    assert split_evenly(total, count) == expected


def test_split_always_sums_to_total_and_never_goes_negative():
    for total in range(0, 101):
        for count in range(1, 13):
            parts = split_evenly(total, count)

            assert len(parts) == count, (total, count)
            assert sum(parts) == total, (total, count)
            assert min(parts) >= 0, (total, count)


def test_rebalance_keeps_pinned_shares():
    # Как в видео: закреплены 25, вернули оффер, двое свободных делят 75.
    assert rebalance([0, 25, 25], [False, True, False]) == [38, 25, 37]


def test_rebalance_without_free_offers_changes_nothing():
    assert rebalance([40, 20], [True, True]) == [40, 20]


def test_rebalance_ignores_old_shares_of_free_offers():
    assert rebalance([90, 5, 5, 0], [False, False, False, False]) == [25, 25, 25, 25]
