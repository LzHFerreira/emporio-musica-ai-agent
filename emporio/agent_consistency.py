"""Check that numeric and policy claims in a reply appear in the evidence."""

import re
from collections.abc import Callable
from typing import Any

from emporio.agent_availability import availability_bound
from emporio.agent_claims import _catalog_rows, _named_products, plain_text

UNIT = re.compile(r"(\d+)\s*(?:\([^)]*\)\s*)?(dia|ano|mes|semana|hora)(?:e?s)?(\s+uteis)?\b")
USED = re.compile(r"\b(?:usad\w*|usou|usei|utilizad\w*)\b")
GROUNDED_PHRASES = (
    "vitalici",
    "qualquer valor",
    "sem parcela minima",
    "bem avaliad",
    "mais vendid",
)
CLOSED_DAY = re.compile(r"domingo|feriado")
OPENING = re.compile(r"\b(?:abr\w*|aberto|aberta|funcion\w*)\b")
HOURS_RANGE = re.compile(r"\b(?:das?|de) (\d{1,2}(?::\d{2})?) (?:as|a) (\d{1,2}(?::\d{2})?)\b")
PIX_STACKING = re.compile(
    r"\b(?:mais|adicional|alem|acumul|cumulativ|soma|sobre (?:esse|este|o) (?:valor|preco))"
)
ENTITLEMENT = re.compile(r"\bpode(?:ra)?\s+(?:sim\s+)?(?:devolver|solicitar a devolucao)")


def consistency_checks(text: str, evidence: list[Any]) -> list[tuple[str, Callable[[], bool]]]:
    """Name each consistency check in the order the guard applies it."""
    found = plain_text(_evidence_text(evidence))
    plain = plain_text(text)
    return [
        ("units", lambda: set(UNIT.findall(plain)) <= set(UNIT.findall(found))),
        ("closed_days", lambda: _closed_days_respected(plain, found)),
        ("hours_order", lambda: _hours_ordered(plain)),
        ("phrases", lambda: _grounded_phrases_present(plain, found)),
        ("entitlement", lambda: _entitlement_conditioned(plain)),
        ("availability", lambda: availability_bound(text, evidence)),
        ("pix_stacking", lambda: pix_not_stacked(text, evidence)),
    ]


def pix_not_stacked(text: str, evidence: list[Any]) -> bool:
    """Reject a PIX discount claimed on top of a promotional catalog price."""
    plain = plain_text(text)
    promotional = [row for row in _catalog_rows(evidence) if _is_promotional(row)]
    if not _named_products(plain, promotional):
        return True
    return not any(_stacking_sentence(s) for s in re.split(r"[.!?;\n]", plain))


def _is_promotional(row: dict[str, Any]) -> bool:
    return (row.get("promotion") or {}).get("state") == "active"


def _stacking_sentence(sentence: str) -> bool:
    return (
        "pix" in sentence
        and ("desconto" in sentence or "%" in sentence)
        and PIX_STACKING.search(sentence) is not None
        and not re.search(r"\b(?:nao|sem)\b", sentence)
    )


def _grounded_phrases_present(plain: str, found: str) -> bool:
    return all(phrase in found for phrase in GROUNDED_PHRASES if phrase in plain)


def _closed_days_respected(plain: str, found: str) -> bool:
    return "fechado" not in found or not any(
        CLOSED_DAY.search(s) and OPENING.search(s) and not re.search(r"nao|fechad", s)
        for s in re.split(r"[.!?;\n]", plain)
    )


def _hours_ordered(plain: str) -> bool:
    return all(_minutes(a) < _minutes(b) for a, b in HOURS_RANGE.findall(plain))


def _minutes(clock: str) -> int:
    hour, _, minute = clock.partition(":")
    return int(hour) * 60 + int(minute or 0)


def _entitlement_conditioned(plain: str) -> bool:
    if any(ENTITLEMENT.search(s) and USED.search(s) for s in re.split(r"[.!?;\n]", plain)):
        return False
    return not ENTITLEMENT.search(plain) or (
        "dias" in plain
        and any(term in plain for term in ("online", "site", "internet", "recebimento"))
    )


def _evidence_text(evidence: list[Any]) -> str:
    parts = [item.get("data", item) if isinstance(item, dict) else item for item in evidence]
    return " ".join(str(part) for part in parts)
