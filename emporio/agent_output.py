"""Conservatively check model output against returned public evidence."""

import re
from typing import Any

from emporio.agent_claims import contacts_grounded, plain_text, specific_claims_supported
from emporio.agent_numbers import numbers_supported


def output_supported(
    text: str, outcome: str, sources: list[dict[str, Any]], evidence: list[Any]
) -> bool:
    """Reject ungrounded numbers, personal contacts, and source-category claims."""
    return _supported_response(text, outcome, _source_types(sources), evidence)


def _supported_response(text, outcome, kinds, evidence):
    if outcome not in {"answer", "clarification", "handoff"}:
        return False
    safe_clarification = outcome == "clarification" and _safe_clarification(text)
    if not _text_safe_for_turn(text, safe_clarification, evidence, kinds):
        return False
    if safe_clarification:
        return True
    return _claims_supported(text, kinds, evidence)


def _text_safe_for_turn(text, safe_clarification, evidence, kinds):
    if not _safe_text(text) or not contacts_grounded(text, evidence, kinds):
        return False
    return safe_clarification or numbers_supported(text, evidence)


def _claims_supported(text, kinds, evidence):
    plain = plain_text(text)
    if _scope_only_response(plain):
        return specific_claims_supported(plain, kinds, evidence)
    return _claim_sources(plain, kinds) and specific_claims_supported(plain, kinds, evidence)


def _scope_only_response(text):
    has_offer = "posso ajudar" in text or "sou o assistente" in text
    return has_offer and not _contains_factual_claim(text)


def _contains_factual_claim(text):
    cues = (" custa ", " esta disponivel", " fica na ", " tem ", " r$ ", " preco de ", " preco e ")
    return any(cue in f" {text} " for cue in cues)


def _safe_clarification(text: str) -> bool:
    """Allow preference questions while keeping factual claims evidence-gated."""
    plain = plain_text(text).strip()
    return (
        text.rstrip().endswith("?")
        and _is_preference_question(plain)
        and not _has_store_claim(plain)
    )


def _is_preference_question(plain: str) -> bool:
    cues = (
        "voce prefere ",
        "prefere ",
        "qual faixa de preco",
        "qual e seu orcamento",
        "qual voce prefere",
        "qual prefere",
    )
    return any(cue in plain for cue in cues) or " ou " in plain and not _has_store_claim(plain)


def _has_store_claim(plain: str) -> bool:
    cues = (" custa ", " preco e ", " fica na ", " endereco ", " esta disponivel")
    return any(cue in plain for cue in cues)


def _source_types(sources: list[dict[str, Any]]) -> set[str]:
    return {kind for source in sources if isinstance((kind := source.get("type")), str)}


def _safe_text(text: str) -> bool:
    return (
        len(text) <= 2048
        and re.search(r"\b(?:produto|product)\s+#?\d+\b", plain_text(text)) is None
    )


def _claim_sources(text: str, kinds: set[str]) -> bool:
    return _catalog_supported(text, kinds) and _policy_supported(text, kinds)


def _catalog_supported(text: str, kinds: set[str]) -> bool:
    words = ("disponivel", "estoque", "preco", "violao", "guitarra", "instrumento")
    return not any(word in text for word in words) or "catalog" in kinds


def _policy_supported(text: str, kinds: set[str]) -> bool:
    words = ("devolu", "reembolso", "horario", "garantia", "frete", "pix")
    return not any(word in text for word in words) or "policy" in kinds
