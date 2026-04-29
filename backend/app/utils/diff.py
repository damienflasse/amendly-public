"""
Word-level diff engine for Amendly.

Computes a token-by-token diff between two text strings using Python's
built-in difflib.SequenceMatcher.  Each token represents a word (whitespace-
delimited) so that the result maps directly to the inline diff UI in the
frontend: additions are highlighted, deletions are struck through, and equal
runs are shown as-is.

Exported symbols:
    DiffToken  — TypedDict describing a single diff token.
    compute_diff — Pure function; no side effects, no DB access.
"""

from difflib import SequenceMatcher
from typing import Literal, TypedDict


class DiffToken(TypedDict):
    """A single word-level diff token.

    Attributes:
        text: The word (or reconstructed phrase) represented by this token.
        type: One of ``"equal"``, ``"insert"``, or ``"delete"``.
    """

    text: str
    type: Literal["equal", "insert", "delete"]


def _tokenize(text: str) -> list[str]:
    """Split *text* into word tokens preserving whitespace between words.

    Each word becomes one token; leading/trailing whitespace on the whole
    string is stripped.  An empty string returns an empty list.

    Parameters:
        text: The raw input string.

    Returns:
        A list of non-empty word strings.
    """
    return text.split()


def compute_diff(original: str, proposed: str) -> list[DiffToken]:
    """Compute a word-level diff between *original* and *proposed*.

    Uses :class:`difflib.SequenceMatcher` on word-split tokens.  Consecutive
    words within the same opcode are joined with a single space so that the
    frontend renders them as readable phrases rather than isolated words.

    Parameters:
        original: The text being amended (may be empty).
        proposed: The author's replacement text (may be empty).

    Returns:
        An ordered list of :class:`DiffToken` dicts, each with ``text`` and
        ``type`` keys.  The list covers every word in both inputs; concatenating
        all ``text`` values (with spaces) reconstructs both sides of the diff.

    Side effects:
        None — pure function.

    Example::

        >>> compute_diff("The quick brown fox", "A swift brown fox")
        [
            {"text": "The quick", "type": "delete"},
            {"text": "A swift",   "type": "insert"},
            {"text": "brown fox", "type": "equal"},
        ]
    """
    a_tokens = _tokenize(original)
    b_tokens = _tokenize(proposed)

    # Handle degenerate cases up-front so the matcher never sees empty lists.
    if not a_tokens and not b_tokens:
        return []
    if not a_tokens:
        return [DiffToken(text=" ".join(b_tokens), type="insert")]
    if not b_tokens:
        return [DiffToken(text=" ".join(a_tokens), type="delete")]

    matcher = SequenceMatcher(None, a_tokens, b_tokens, autojunk=False)
    tokens: list[DiffToken] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            tokens.append(DiffToken(text=" ".join(a_tokens[i1:i2]), type="equal"))
        elif tag == "replace":
            tokens.append(DiffToken(text=" ".join(a_tokens[i1:i2]), type="delete"))
            tokens.append(DiffToken(text=" ".join(b_tokens[j1:j2]), type="insert"))
        elif tag == "delete":
            tokens.append(DiffToken(text=" ".join(a_tokens[i1:i2]), type="delete"))
        elif tag == "insert":
            tokens.append(DiffToken(text=" ".join(b_tokens[j1:j2]), type="insert"))

    return tokens
