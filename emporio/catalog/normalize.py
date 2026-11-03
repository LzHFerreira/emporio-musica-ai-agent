"""Normalize Portuguese catalog text for source-backed matching."""

import re
import unicodedata


def normalize_text(value: str) -> str:
    """Casefold text, remove accents, and separate punctuation."""
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(re.sub(r"[\W_]+", " ", plain).split())
