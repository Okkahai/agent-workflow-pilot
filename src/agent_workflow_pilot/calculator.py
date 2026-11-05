"""Basic arithmetic operations for built-in integers and floats."""

import math


def _validate(value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("operands must be integers or floats")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("float operands must be finite")


def add(a: int | float, b: int | float) -> int | float:
    """Return the sum of two finite built-in integers or floats."""
    _validate(a)
    _validate(b)
    return a + b


def subtract(a: int | float, b: int | float) -> int | float:
    """Return the difference of two finite built-in integers or floats."""
    _validate(a)
    _validate(b)
    return a - b


def multiply(a: int | float, b: int | float) -> int | float:
    """Return the product of two finite built-in integers or floats."""
    _validate(a)
    _validate(b)
    return a * b


def divide(a: int | float, b: int | float) -> int | float:
    """Return the quotient, raising ZeroDivisionError when b is zero."""
    _validate(a)
    _validate(b)
    return a / b
