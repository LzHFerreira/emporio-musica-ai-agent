"""Render catalog availability lines for the facts a model cites by ref."""

import re
from decimal import Decimal, InvalidOperation

from emporio.agent_claims import plain_text

UNRENDERED_CLAIM = re.compile(r"r\$\s*\d|\b\d+,\d{2}\b|estoque|disponi|esgotad")
UNRENDERED_ORDER = re.compile(
    r"enviad|entregue|a caminho|cancelad|processando|em processamento|despachad|postad"
    r"|saiu para entrega|rastreio|previsao de entrega"
)

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


def _order_line(row):
    line = f"Pedido {row['order_id']}: {row['status']}"
    if row.get("tracking_code"):
        line += f"; rastreio {row['tracking_code']}"
    if row.get("estimated_delivery"):
        line += f"; previsão de entrega {row['estimated_delivery']}"
    return line + "."


def _line(row):
    if row["ref"].startswith("order-"):
        return _order_line(row)
    label = LABELS.get(row.get("availability"), LABELS["unknown"])
    condition = row.get("payment_condition")
    suffix = f" ({condition})" if condition else ""
    return f"{row['name']}: {label}; {_price(row.get('payable_price_brl'))}{suffix}."


def facts_failure(answer: dict, evidence: list[dict]) -> str | None:
    """Name the facts rule that rejects an answer, or return None when it passes."""
    if re.search(r"(catalog|order)-\d+", answer.get("text", ""), re.IGNORECASE):
        return "facts_leaked_ref"
    rows, plain = evidence_rows(evidence), plain_text(answer["text"])
    if UNRENDERED_CLAIM.search(plain) and any(ref.startswith("catalog-") for ref in rows):
        return "facts_claim"
    if UNRENDERED_ORDER.search(plain) and any(ref.startswith("order-") for ref in rows):
        return "facts_claim"
    if any(ref not in rows for ref in answer.get("facts", [])):
        return "facts_unknown_ref"
    return None


def evidence_rows(evidence: list[dict]) -> dict[str, dict]:
    """Map each fact ref in the evidence to its row."""
    refs = [r for i in evidence for r in i.get("data", []) if isinstance(r, dict) and "ref" in r]
    return {r["ref"]: r for r in refs}


def with_facts(answer: dict | None, evidence: list[dict]) -> dict | None:
    """Append one availability line per fact ref; return None when a ref is rejected."""
    if answer is None or facts_failure(answer, evidence):
        return None
    if "facts" not in answer:
        return answer
    rows = evidence_rows(evidence)
    lines = [_line(rows[k]) for k in answer["facts"]]
    rendered = {k: v for k, v in answer.items() if k != "facts"}
    rendered["text"] = "\n".join([answer["text"], *lines])
    return rendered
