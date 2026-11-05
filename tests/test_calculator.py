import pytest

from agent_workflow_pilot.calculator import add, divide, multiply, subtract


@pytest.mark.parametrize(
    ("operation", "a", "b", "expected"),
    [
        (add, 2, 3, 5),
        (add, -2, 0, -2),
        (add, 1, 2.5, 3.5),
        (subtract, 2, 3, -1),
        (subtract, -2, -3, 1),
        (subtract, 2.5, 1, 1.5),
        (multiply, 2, 3, 6),
        (multiply, -2, 3, -6),
        (multiply, 0, 3.5, 0.0),
        (divide, 6, 3, 2.0),
        (divide, -6, 2, -3.0),
        (divide, 5, 2, 2.5),
    ],
)
def test_operations(operation, a, b, expected):
    assert operation(a, b) == expected


@pytest.mark.parametrize("operation", [add, subtract, multiply, divide])
@pytest.mark.parametrize("bad_value", [True, False, "1", None, 1j, [], object()])
@pytest.mark.parametrize("bad_position", [0, 1])
def test_rejects_non_integer_and_non_float_operands(operation, bad_value, bad_position):
    operands = [2, 3]
    operands[bad_position] = bad_value
    with pytest.raises(TypeError):
        operation(*operands)


@pytest.mark.parametrize("operation", [add, subtract, multiply, divide])
@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
@pytest.mark.parametrize("bad_position", [0, 1])
def test_rejects_non_finite_float_operands(operation, bad_value, bad_position):
    operands = [2, 3]
    operands[bad_position] = bad_value
    with pytest.raises(ValueError):
        operation(*operands)


@pytest.mark.parametrize("zero", [0, 0.0, -0.0])
def test_divide_by_zero_raises(zero):
    with pytest.raises(ZeroDivisionError):
        divide(1, zero)
