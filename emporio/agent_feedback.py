"""Tell the model which unsupported claim got its draft rejected."""

from typing import Any

from emporio.agent_numbers import NUMBER, _decimal, _evidence_numbers
from emporio.agent_protocol import REJECTED_TEXT

HINTS = {
    "catalog_source": "Consulte search_catalog antes de citar produtos, preços ou estoque.",
    "policy_source": "Consulte lookup_public_policy antes de citar regras da loja.",
}


def rejection_feedback(check: str, answer: dict[str, Any] | None, evidence: list[Any]) -> str:
    """Return the rejection notice, naming unsupported numbers or the missing source tool."""
    if check == "numbers" and answer:
        return f"{REJECTED_TEXT} {_numbers_hint(answer['text'], evidence)}"
    hint = HINTS.get(check)
    return f"{REJECTED_TEXT} {hint}" if hint else REJECTED_TEXT


def _numbers_hint(text: str, evidence: list[Any]) -> str:
    known = _evidence_numbers(evidence)
    tokens = list(dict.fromkeys(m for m in NUMBER.findall(text) if _decimal(m) not in known))
    return (
        f"Estes números não aparecem nas fontes: {', '.join(tokens)}; "
        "não repita números do cliente nem cite páginas ou seções."
    )
