"""Descriptive statistics for finite integers and floats."""

from collections.abc import Iterable
import math
import statistics as _statistics


def _validated(values: Iterable[int | float]) -> list[int | float]:
    data = list(values)
    if not data:
        raise ValueError("statistics require at least one value")
    for value in data:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("values must be integers or floats")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("float values must be finite")
    return data


def mean(values: Iterable[int | float]) -> int | float:
    """Return the arithmetic mean without mutating the input.

    Empty or non-finite input raises ValueError; non-numeric values and
    booleans raise TypeError. An unrepresentable fractional result raises
    OverflowError. Single-pass iterables are supported.
    """
    return _statistics.mean(_validated(values))


def median(values: Iterable[int | float]) -> int | float:
    """Return the middle value, averaging the middle pair for even counts.

    Input is not mutated. Empty or non-finite input raises ValueError;
    non-numeric values and booleans raise TypeError. An unrepresentable
    fractional result raises OverflowError. Iterators are supported.
    """
    data = sorted(_validated(values))
    middle = len(data) // 2
    if len(data) % 2:
        return data[middle]
    return _statistics.mean(data[middle - 1 : middle + 1])
