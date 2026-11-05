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
    booleans raise TypeError. Single-pass iterables are supported.
    """
    return _statistics.mean(_validated(values))


def median(values: Iterable[int | float]) -> int | float:
    """Return the middle value, averaging the middle pair for even counts.

    Input is not mutated. Empty or non-finite input raises ValueError;
    non-numeric values and booleans raise TypeError. Iterators are supported.
    """
    return _statistics.median(_validated(values))
