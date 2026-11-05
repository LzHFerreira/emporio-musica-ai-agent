"""Conservatively check model output against returned public evidence."""

import re
from collections.abc import Callable
from typing import Any

from emporio.agent_claims import (
    POLICY_WORDS,
    _address_grounded,
    _product_price_bound,
    _shipping_polarity_grounded,
    _topic_numbers_grounded,
    contacts_grounded,
    plain_text,
)
from emporio.agent_consistency import consistency_checks
from emporio.agent_numbers import numbers_supported, scrub
from emporio.agent_render import facts_failure

Check = tuple[str, Callable[[], bool]]


def output_supported(
    text: str, outcome: str, sources: list[dict[str, Any]], evidence: list[Any]
) -> bool:
    """Reject ungrounded numbers, personal contacts, and source-category claims."""
    return first_failed_check(text, outcome, sources, evidence) is None


def first_failed_check(
    text: str, outcome: str, sources: list[dict[str, Any]], evidence: list[Any], customer=""
) -> str | None:
    """Return the name of the first check that rejects the draft, or None."""
    kinds, checked = _source_types(sources), scrub({"text": text}, customer)
    for name, passes in _checks(checked, outcome, kinds, evidence):
        if not passes():
            return name
    return None


def rejection_trace(
    answer: dict[str, Any] | None, sources: list[dict[str, Any]], evidence: list[Any], customer=""
) -> dict[str, str]:
    """Return the operation record for a rejected draft; the draft text is not stored."""
    if answer is None:
        return {"tool": "output_check", "outcome": "rejected", "check": "invalid_terminal"}
    check = facts_failure(answer, evidence) or first_failed_check(
        answer["text"], answer["outcome"], sources, evidence, customer
    )
    return {"tool": "output_check", "outcome": "rejected", "check": check or "unknown"}


def _checks(text: str, outcome: str, kinds: set[str], evidence: list[Any]) -> list[Check]:
    plain = plain_text(text)
    safe = outcome == "clarification" and _safe_clarification(text)
    return [
        *_front_checks(text, outcome, kinds, evidence, safe),
        *_claim_checks(plain, kinds, evidence, safe),
        *consistency_checks(text, evidence),
    ]


def _front_checks(text, outcome, kinds, evidence, safe) -> list[Check]:
    return [
        ("outcome", lambda: outcome in {"answer", "clarification", "handoff"}),
        ("unsafe_text", lambda: _safe_text(text)),
        ("contacts", lambda: contacts_grounded(text, evidence, kinds)),
        ("numbers", lambda: safe or numbers_supported(text, evidence)),
    ]


def _claim_checks(plain, kinds, evidence, safe) -> list[Check]:
    if safe:
        return []
    scoped = _scope_only_response(plain)
    return [
        ("no_evidence", lambda: scoped or bool(evidence)),
        ("catalog_source", lambda: scoped or _catalog_supported(plain, kinds)),
        ("policy_source", lambda: scoped or _policy_supported(plain, kinds)),
        ("address", lambda: _address_grounded(plain, evidence)),
        ("price_binding", lambda: _product_price_bound(plain, kinds, evidence)),
        ("shipping", lambda: _shipping_polarity_grounded(plain, evidence)),
        ("topic_numbers", lambda: _topic_numbers_grounded(plain, evidence)),
    ]


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


def _catalog_supported(text: str, kinds: set[str]) -> bool:
    words = ["disponivel", "estoque"]
    if "r$" in text:
        words += ["preco", "violao", "guitarra", "instrumento"]
    return not any(word in text for word in words) or "catalog" in kinds


def _policy_supported(text: str, kinds: set[str]) -> bool:
    words = POLICY_WORDS
    return not any(word in text for word in words) or "policy" in kinds
