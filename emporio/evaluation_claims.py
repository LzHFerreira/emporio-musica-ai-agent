"""Critical-claim matching for evaluation replies."""

import re
import unicodedata
from typing import Any


def critical_hit(case: dict[str, Any], text: str) -> bool:
    """Return whether the reply states a critical claim of the case.

    Args:
        case: Evaluation case whose optional `critical` list holds claim patterns.
        text: Model reply, matched after accent and case folding.
    """
    return any(re.search(item["claim"], fold(text)) for item in case.get("critical", []))


def fold(text: str) -> str:
    """Return the text lowercased with accents removed."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char)).lower()
