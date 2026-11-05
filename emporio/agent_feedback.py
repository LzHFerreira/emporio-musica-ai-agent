"""Tell the model which unsupported claim got its draft rejected."""

from typing import Any

from emporio.agent_numbers import NUMBER, _decimal, _evidence_numbers
from emporio.agent_protocol import REJECTED_TEXT
from emporio.agent_render import evidence_rows

FACTS_HINT = (
    'Não escreva preços, estoque ou status de pedido no texto; selecione as refs em "facts".'
)
HINTS = {
    "catalog_source": "Consulte search_catalog antes de citar produtos, preços ou estoque.",
    "policy_source": "Consulte lookup_public_policy antes de citar regras da loja.",
}


def rejection_feedback(check: str, answer: dict[str, Any] | None, evidence: list[Any]) -> str:
    """Return the rejection notice, naming unsupported numbers or the missing source tool."""
    if check == "numbers" and answer:
        return f"{REJECTED_TEXT} {_numbers_hint(answer['text'], evidence)}"
    if check == "facts_claim":
        return f"{REJECTED_TEXT} {FACTS_HINT} Refs disponíveis: {_ref_names(evidence)}."
    hint = HINTS.get(check)
    return f"{REJECTED_TEXT} {hint}" if hint else REJECTED_TEXT


def _ref_names(evidence: list[Any]) -> str:
    rows = evidence_rows(evidence)
    names = [f"{k} = {_label(k, r)}" for k, r in rows.items()]
    return "; ".join(names)


def _label(ref: str, row: dict) -> str:
    return row["name"] if ref.startswith("catalog-") else f"Pedido {row['order_id']}"


def _numbers_hint(text: str, evidence: list[Any]) -> str:
    known = _evidence_numbers(evidence)
    tokens = list(dict.fromkeys(m for m in NUMBER.findall(text) if _decimal(m) not in known))
    return (
        f"Estes números não aparecem nas fontes: {', '.join(tokens)}; "
        'só repita números do cliente atribuindo-os a ele ("pelo que você informou") '
        "e não cite páginas ou seções."
    )
