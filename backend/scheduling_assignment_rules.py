"""Pure ordering rules shared by assignment preview and demo seeding."""

from typing import TypeVar

T = TypeVar("T")


def snake_candidate_index(pool_size: int, class_index: int) -> int | None:
    """Return the pool index for one class in ascending/descending snake order."""
    if pool_size <= 0 or class_index < 0:
        return None
    if pool_size == 1:
        return 0
    row, index = divmod(class_index, pool_size)
    if row % 2:
        index = pool_size - 1 - index
    return index


def snake_order(items: list[T]) -> list[T]:
    """Order parallel classes as first, last, second, penultimate, and so on."""
    if not items:
        return []
    return items[:1] + list(reversed(items[1:]))
