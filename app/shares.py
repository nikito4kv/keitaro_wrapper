"""Как делятся доли между офферами потока. Правило снято с работающего редактора (см. README).

Незакреплённые офферы делят свободные проценты поровну. Проценты целые, поэтому поровну
выходит не всегда: все офферы, кроме последнего, получают округлённое среднее,
последний забирает остаток.

    100 на троих      -> 33, 33, 34
    75 на двоих       -> 38, 37   (25 закреплено за третьим)
    100 на четверых   -> 25, 25, 25, 25
"""

FULL = 100


def split_evenly(total: int, count: int) -> list[int]:
    """Делит total на count целых частей, которые в сумме дают ровно total."""
    if count <= 0:
        return []
    total = max(0, total)
    base = round(total / count)
    # Когда свободных процентов меньше, чем офферов, округление вверх ушло бы в минус.
    if base * (count - 1) > total:
        base = total // count
    return [base] * (count - 1) + [total - base * (count - 1)]


def rebalance(shares: list[int], pinned: list[bool]) -> list[int]:
    """Пересчитывает доли офферов потока. Закреплённые не меняются, остальные делят остаток до 100."""
    free = FULL - sum(share for share, is_pinned in zip(shares, pinned) if is_pinned)
    parts = iter(split_evenly(free, pinned.count(False)))
    return [share if is_pinned else next(parts) for share, is_pinned in zip(shares, pinned)]
