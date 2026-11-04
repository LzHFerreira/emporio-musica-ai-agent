"""Check that numeric and policy claims in a reply appear in the evidence."""

import re
from collections.abc import Callable
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
ENTITLEMENT = re.compile(r"\bpode(?:ra)?\s+(?:sim\s+)?(?:devolver|solicitar a devolucao)")


def consistency_checks(text: str, evidence: list[Any]) -> list[tuple[str, Callable[[], bool]]]:
    """Name each consistency check in the order the guard applies it."""
    found = plain_text(_evidence_text(evidence))
    plain = plain_text(text)
    return [
        ("units", lambda: set(UNIT.findall(plain)) <= set(UNIT.findall(found))),
        ("closed_days", lambda: _closed_days_respected(plain, found)),
        ("phrases", lambda: _grounded_phrases_present(plain, found)),
        ("entitlement", lambda: _entitlement_conditioned(plain)),
    ]


def _grounded_phrases_present(plain: str, found: str) -> bool:
    return all(phrase in found for phrase in GROUNDED_PHRASES if phrase in plain)


def _closed_days_respected(plain: str, found: str) -> bool:
    return "fechado" not in found or not any(
        CLOSED_DAY.search(s) and OPENING.search(s) and not re.search(r"nao|fechad", s)
        for s in re.split(r"[.!?;\n]", plain)
    )


def _entitlement_conditioned(plain: str) -> bool:
    return not ENTITLEMENT.search(plain) or (
        "dias" in plain
        and any(term in plain for term in ("online", "site", "internet", "recebimento"))
    )


def _evidence_text(evidence: list[Any]) -> str:
    parts = [item.get("data", item) if isinstance(item, dict) else item for item in evidence]
    return " ".join(str(part) for part in parts)
