import pytest

from agent_workflow_pilot.statistics import mean, median


@pytest.mark.parametrize(
    ("operation", "values", "expected"),
    [
        (mean, [1, 2, 6], 3),
        (mean, [-3, 0, 1.5], -0.5),
        (mean, [7], 7),
        (mean, [1e16, 1, -1e16], 1 / 3),
        (median, [9, 1, 3], 3),
        (median, [9, 1, 5, 3], 4),
        (median, [-3, 0, 1.5], 0),
        (median, [7], 7),
    ],
)
def test_statistics(operation, values, expected):
    original = values.copy()
    assert operation(values) == pytest.approx(expected)
    assert values == original


@pytest.mark.parametrize("operation", [mean, median])
def test_accepts_single_pass_iterables(operation):
    assert operation(value for value in [3, 1, 2]) == 2


def test_median_avoids_overflow_for_large_finite_values():
    assert median([1e308, 1e308]) == 1e308
    assert median([2**1100, 2**1100 + 2]) == 2**1100 + 1


@pytest.mark.parametrize("operation", [mean, median])
def test_rejects_empty_input(operation):
    with pytest.raises(ValueError):
        operation(iter(()))


@pytest.mark.parametrize("operation", [mean, median])
@pytest.mark.parametrize("bad_value", [True, False, "1", None, 1j, [], object()])
def test_rejects_invalid_values(operation, bad_value):
    with pytest.raises(TypeError):
        operation([1, bad_value, 3])


@pytest.mark.parametrize("operation", [mean, median])
@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
def test_rejects_non_finite_values(operation, bad_value):
    with pytest.raises(ValueError):
        operation([1, bad_value, 3])
