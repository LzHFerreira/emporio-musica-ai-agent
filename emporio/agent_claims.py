"""Check explicit price, address, shipping and public-contact claims."""

import re
import unicodedata
from typing import Any

from emporio.agent_numbers import numbers_supported

POLICY_WORDS = ("devolu", "reembolso", "horario", "garantia", "frete", "pix", "troca")


def specific_claims_supported(text: str, kinds: set[str], evidence: list[Any]) -> bool:
    """Validate claims whose meaning depends on the source record itself."""
    return (
        _address_grounded(text, evidence)
        and _product_price_bound(text, kinds, evidence)
        and (_shipping_polarity_grounded(text, evidence))
        and _topic_numbers_grounded(text, evidence)
    )


def _address_grounded(text: str, evidence: list[Any]) -> bool:
    claim = _address_words(text)
    return not claim or _address_in_evidence(claim, evidence)


def _address_words(text: str) -> list[str]:
    words = re.findall(r"\w+", text)
    marker = _address_marker(words)
    if marker is None:
        return []
    claim = words[words.index(marker) :]
    if "e" in claim:
        claim = claim[: claim.index("e")]
    return [word for word in claim if word not in {"a", "o", "da", "do", "e"}]


def _address_marker(words):
    for term in ("rua", "avenida", "logradouro", "cep", "endereco"):
        if term in words:
            return term
    return None


def _address_in_evidence(claim, evidence):
    source = " ".join(
        " ".join(re.findall(r"\w+", plain_text(_evidence_text(item)))) for item in evidence
    )
    return len(claim) > 1 and " ".join(claim) in source


def _product_price_bound(text: str, kinds: set[str], evidence: list[Any]) -> bool:
    if "catalog" not in kinds:
        return True
    rows = _catalog_rows(evidence)
    if not _has_named_rows(rows):
        return True
    claims = [claim for chunk in _price_chunks(text) for claim in _price_mentions(chunk)]
    return _all_product_prices_supported(claims, rows)


def _has_named_rows(rows):
    return any(isinstance(row.get("name"), str) for row in rows)


def _all_product_prices_supported(claims, rows):
    return all(_price_claim_supported(amount, clause, rows) for amount, clause in claims)


def _price_claim_supported(amount: str, clause: str, rows: list[dict[str, Any]]) -> bool:
    named = _named_products(clause, rows)
    if named:
        return _matching_product_price(named, amount)
    return not _has_product_reference(clause)


def _named_products(clause, rows):
    return [row for row in rows if _name_mentioned(clause, row.get("name", ""), rows)]


def _matching_product_price(rows, amount):
    return any(_row_has_price(row, amount) for row in rows)


def _has_product_reference(clause):
    terms = (" custa ", " violao ", " guitarra ", " modelo ", " produto ")
    return (
        any(term in f" {clause} " for term in terms)
        or re.search(r"\b[a-z]{1,5}\d+[a-z0-9]*\b", clause) is not None
    )


def _catalog_rows(evidence: list[Any]) -> list[dict[str, Any]]:
    rows = []
    for item in evidence:
        rows.extend(_catalog_rows_from(item))
    return rows


def _catalog_rows_from(item):
    if not isinstance(item, dict):
        return []
    if isinstance(item.get("name"), str):
        return [item]
    return [row for row in item.get("data", []) if isinstance(row, dict)]


def _price_chunks(text: str) -> list[str]:
    return re.split(r"\s+e\s+|;\s*|\.\s+|,\s+|\n(?=\s*(?:[-*•]|\d{1,2}[.)])\s)", text)


def _price_mentions(text: str) -> list[tuple[str, str]]:
    pattern = r"r\$\s*([\d.,]+)|(?:custa|preco|valor)(?:\s+(?:de|e))?\s+([\d.,]+)"
    return [((one or two).rstrip(".,"), text) for one, two in re.findall(pattern, text)]


def _name_mentioned(text: str, name: str, rows: list[dict[str, Any]]) -> bool:
    generic = set("violao guitarra instrumento dreadnought natural sunburst eletrico".split())
    distinctive = set(plain_text(name).split()) - generic
    siblings = [
        set(plain_text(row["name"]).split()) - generic
        for row in rows
        if isinstance(row.get("name"), str) and row.get("name") != name
    ]
    shared = set().union(*(distinctive & sibling for sibling in siblings))
    terms = distinctive - shared
    return bool(terms & set(re.findall(r"\w+", text)))


def _row_has_price(row: dict[str, Any], amount: str) -> bool:
    prices = {
        key: row[key] for key in ("base_price_brl", "payable_price_brl") if row.get(key) is not None
    }
    return bool(prices) and numbers_supported(amount, [prices])


def _shipping_polarity_grounded(text: str, evidence: list[Any]) -> bool:
    if "frete" not in text or "devol" not in text:
        return True
    party = _shipping_party(text)
    return party is None or any(
        _shipping_party(plain_text(_evidence_text(item))) == party for item in evidence
    )


def _topic_numbers_grounded(text: str, evidence: list[Any]) -> bool:
    rows = [row for item in evidence if isinstance(item, dict) for row in item.get("data", [item])]
    return all(
        numbers_supported(sentence, [r for r in rows if term in plain_text(_evidence_text(r))])
        for sentence in re.split(r"[!?;]|\.(?!\d)", re.sub(r"r\$\s*[\d.,]+", "", text))
        for term in POLICY_WORDS
        if term in sentence
    )


SHIPPING_PARTIES = {
    "cliente": "por conta do cliente|cliente paga (?:o )?frete|pago pelo cliente",
    "loja": "por conta da loja|loja paga (?:o )?frete|pag[oa] pela loja",
}


def _shipping_party(text: str) -> str | None:
    for party, pattern in SHIPPING_PARTIES.items():
        if match := re.search(rf"(\bnao\s+(?:e\s+|sera\s+|fica\s+)?)?(?:{pattern})", text):
            return ("loja" if party == "cliente" else "cliente") if match[1] else party
    return None


def contacts_grounded(text: str, evidence: list[Any], kinds: set[str]) -> bool:
    """Require email claims to exactly match reviewed public policy evidence."""
    emails = re.findall(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text)
    available = _policy_emails(evidence, kinds)
    return (
        not emails or "policy" in kinds and all(_email_key(email) in available for email in emails)
    )


def _policy_emails(evidence: list[Any], kinds: set[str]) -> set[str]:
    if "policy" not in kinds:
        return set()
    return {
        _email_key(value) for item in evidence if _policy_evidence(item) for value in _emails(item)
    }


def _policy_evidence(item):
    sources = item.get("sources") if isinstance(item, dict) else None
    return not sources or any(_is_policy_source(source) for source in sources)


def _is_policy_source(source):
    return isinstance(source, dict) and source.get("type") == "policy"


def _emails(item):
    return re.findall(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", _evidence_text(item))


def _email_key(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


def _evidence_text(item: Any) -> str:
    return str(item.get("data", item)) if isinstance(item, dict) else str(item)


def plain_text(text: str) -> str:
    """Fold accents and case for Portuguese lexical evidence checks."""
    value = unicodedata.normalize("NFKD", text.lower())
    return "".join(char for char in value if not unicodedata.combining(char))
