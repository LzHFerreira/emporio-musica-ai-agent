"""Conservatively check model output against returned public evidence."""

import re
from typing import Any

from emporio.agent_claims import (
    POLICY_WORDS,
    contacts_grounded,
    plain_text,
    specific_claims_supported,
)
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
    return (
        bool(evidence)
        and _claim_sources(plain, kinds)
        and specific_claims_supported(plain, kinds, evidence)
    )


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
        and re.search(r"[.!]\s", text) is None
        and _is_preference_question(plain)
        and not _has_store_claim(plain)
        and not _mentions_price_or_policy(plain)
    )


def _mentions_price_or_policy(plain: str) -> bool:
    return "r$" in plain or any(word in plain for word in POLICY_WORDS)


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
        and "<|" not in text
        and re.search(r"\b(?:produto|product)\s+#?\d+\b", plain_text(text)) is None
        and not _degenerate(text)
        and not _english_leak(text)
    )


def _english_leak(text: str) -> bool:
    words = set(re.findall(r"[a-z']+", text.lower()))
    return len(words & set("the is and you with this that are it's for your".split())) >= 2


def _degenerate(text: str) -> bool:
    """Detect repeated 1-6 token loops and replies cut off at a trailing colon."""
    tokens = [m.group() for m in re.finditer(r"\w+|([^\w\s])\1*", plain_text(text))]
    looped = any(
        tokens[i : i + n]
        == tokens[i + n : i + 2 * n]
        == tokens[i + 2 * n : i + 3 * n]
        == tokens[i + 3 * n : i + 4 * n]
        for n in range(1, 7)
        for i in range(len(tokens) - 4 * n + 1)
    )
    return looped or re.search(r":[^\w.!?]*$", text.rstrip()) is not None


def _claim_sources(text: str, kinds: set[str]) -> bool:
    return _catalog_supported(text, kinds) and _policy_supported(text, kinds)


def _catalog_supported(text: str, kinds: set[str]) -> bool:
    words = ("disponivel", "estoque", "preco", "violao", "guitarra", "instrumento")
    return not any(word in text for word in words) or "catalog" in kinds


def _policy_supported(text: str, kinds: set[str]) -> bool:
    words = POLICY_WORDS
    return not any(word in text for word in words) or "policy" in kinds
