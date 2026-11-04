"""Check that availability claims about named catalog products match their evidence."""

import re
from typing import Any

from emporio.agent_claims import _catalog_rows, _named_products, _price_chunks, plain_text

NEGATIVE = re.compile(
    r"sem estoque|esgotad|indisponi|fora de estoque|em falta"
    r"|nao (?:esta|temos|tem) (?:disponivel|em estoque)"
)
POSITIVE = re.compile(r"disponivel|em estoque")


def availability_bound(text: str, evidence: list[Any]) -> bool:
    """Require each named product's availability claim to match its catalog row."""
    rows = _catalog_rows(evidence)
    return all(_clause_supported(clause, rows) for clause in _price_chunks(plain_text(text)))


def _clause_supported(clause: str, rows: list[dict[str, Any]]) -> bool:
    named = _named_products(clause, rows)
    if NEGATIVE.search(clause):
        return not any(row.get("availability") in {"available", "unknown"} for row in named)
    if POSITIVE.search(clause):
        return all(row.get("availability") == "available" for row in named)
    return True
