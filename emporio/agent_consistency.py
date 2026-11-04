"""Check that numeric and policy claims in a reply appear in the evidence."""

import re
from typing import Any

from emporio.agent_claims import plain_text

UNIT = re.compile(r"(\d+)\s*(?:\([^)]*\)\s*)?(dia|ano|mes|semana|hora)(?:e?s)?\b")
GROUNDED_PHRASES = (
    "vitalici",
    "qualquer valor",
    "sem parcela minima",
    "bem avaliad",
    "mais vendid",
)
CLOSED_DAY = re.compile(r"domingo|feriado")
OPENING = re.compile(r"\b(?:abr\w*|aberto|aberta|funcion\w*)\b")


def claims_consistent(text: str, evidence: list[Any]) -> bool:
    """Require every number-unit pair and grounded phrase in text to be in evidence."""
    found = plain_text(_evidence_text(evidence))
    plain = plain_text(text)
    pairs_ok = set(UNIT.findall(plain)) <= set(UNIT.findall(found))
    return (
        pairs_ok
        and _closed_days_respected(plain, found)
        and all(phrase in found for phrase in GROUNDED_PHRASES if phrase in plain)
    )


def _closed_days_respected(plain: str, found: str) -> bool:
    return "fechado" not in found or not any(
        CLOSED_DAY.search(s) and OPENING.search(s) and not re.search(r"nao|fechad", s)
        for s in re.split(r"[.!?;\n]", plain)
    )


def _evidence_text(evidence: list[Any]) -> str:
    parts = [item.get("data", item) if isinstance(item, dict) else item for item in evidence]
    return " ".join(str(part) for part in parts)
