import pytest

from agent_workflow_pilot.string_normalization import normalize_whitespace


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", ""),
        (" \t\r\n", ""),
        ("  hello  world  ", "hello world"),
        ("hello\tworld\r\nagain", "hello world again"),
        ("\u00a0hello\u2003world\u202f", "hello world"),
        ("Hello, WORLD!", "Hello, WORLD!"),
        ("  caf\u00e9  e\u0301  \u6771\u4eac  ", "caf\u00e9 e\u0301 \u6771\u4eac"),
        ("a\u200bb", "a\u200bb"),
    ],
)
def test_normalize_whitespace(text, expected):
    assert normalize_whitespace(text) == expected


@pytest.mark.parametrize("value", [None, 42, True, b"hello", [], {}])
def test_rejects_non_strings(value):
    with pytest.raises(TypeError):
        normalize_whitespace(value)


def test_normalization_is_idempotent():
    normalized = normalize_whitespace("  hello\t world\n")
    assert normalize_whitespace(normalized) == normalized
