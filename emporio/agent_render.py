"""Render catalog availability lines for the facts a model cites by ref."""

import re
from decimal import Decimal, InvalidOperation

from emporio.agent_claims import plain_text

UNRENDERED_CLAIM = re.compile(r"r\$\s*\d|\b\d+,\d{2}\b|estoque|disponi|esgotad")

LABELS = {
    "available": "disponível em estoque",
    "temporarily_unavailable": "sem estoque no momento",
    "coming_soon": "em breve",
    "discontinued": "fora de linha",
    "unknown": "disponibilidade não confirmada",
}


def _price(value):
    try:
        amount = Decimal(str(value))
    except InvalidOperation:
        amount = Decimal("NaN")
    if not amount.is_finite():
        return "preço não confirmado"
    return "R$ " + f"{amount:,.2f}".translate(str.maketrans(",.", ".,"))


def _line(row):
    label = LABELS.get(row.get("availability"), LABELS["unknown"])
    condition = row.get("payment_condition")
    suffix = f" ({condition})" if condition else ""
    return f"{row['name']}: {label}; {_price(row.get('payable_price_brl'))}{suffix}."


def with_facts(answer: dict | None, evidence: list[dict]) -> dict | None:
    """Append one availability line per fact ref; return None when a ref is unknown."""
    if answer is None or re.search(r"catalog-\d+", answer.get("text", ""), re.IGNORECASE):
        return None
    refs = [r for i in evidence for r in i.get("data", []) if isinstance(r, dict) and "ref" in r]
    rows = {r["ref"]: r for r in refs}
    if UNRENDERED_CLAIM.search(plain_text(answer["text"])) and any(
        ref.startswith("catalog-") for ref in rows
    ):
        return None
    if "facts" not in answer:
        return answer
    if any(ref not in rows for ref in answer["facts"]):
        return None
    lines = [_line(rows[k]) for k in answer["facts"]]
    rendered = {k: v for k, v in answer.items() if k != "facts"}
    rendered["text"] = "\n".join([answer["text"], *lines])
    return rendered
