"""Small string normalization helpers."""


def normalize_whitespace(text: str) -> str:
    """Trim and collapse Unicode whitespace to single ASCII spaces.

    Preserve case, punctuation and all non-whitespace characters. Empty or
    whitespace-only input returns an empty string. Reject non-string input
    with TypeError rather than converting it to text.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return " ".join(text.split())
