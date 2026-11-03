"""Source-bound passage and pricing-rule review validation."""

import hashlib
import json
import re
from typing import cast

from django.core.exceptions import ValidationError

from emporio.catalog.normalize import normalize_text
from emporio.catalog.pricing import percentage_basis_points
from emporio.sources.policy_pdf_extract import MAX_PDF_TEXT_BYTES

RULE_CODE = "pix-full-payment-discount-v1"
TOPICS = {
    "scope",
    "contact",
    "hours",
    "payment",
    "returns",
    "delivery",
    "promotions",
    "warranty",
    "privacy",
    "internal",
    "application",
}
_PERCENT = re.compile(r"(?<!\w)(\d{1,2}(?:[.,]\d{1,2})?)\s*(?:%|percent|por cento)")
_PASSAGE_FIELDS = {"page", "section", "topic", "audience", "conflict", "text"}


def build_review(values, pages: list[str], digest: str, revision: int) -> dict[str, object]:
    """Validate staff attestations and return policy metadata bound to this PDF revision."""
    if values.get("unchanged_rules_attested") != "yes":
        raise ValidationError("confirm review of unchanged policy rules")
    basis_points, passages = _review_values(
        values.get("pix_discount_percent", ""), values.get("passage_reviews", "")
    )
    _check_pix_evidence(pages, basis_points)
    return {
        "pdf_sha256": digest,
        "draft_revision": revision,
        "pricing_rule": {"code": RULE_CODE, "pix_basis_points": basis_points},
        "passages": _validate_passages(passages, pages),
        "unchanged_rules_attested": True,
    }


def _review_values(percent, raw_passages):
    try:
        if len(raw_passages) > MAX_PDF_TEXT_BYTES:
            raise ValueError("policy review exceeds size limit")
        return percentage_basis_points(percent), cast(object, json.loads(raw_passages))
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValidationError("invalid policy review") from error


def _check_pix_evidence(pages: list[str], basis_points: int) -> None:
    for page in pages:
        if _page_has_pix_rate(page, basis_points):
            return
    raise ValidationError("reviewed PIX percentage does not match the policy PDF")


def _page_has_pix_rate(page: str, basis_points: int) -> bool:
    for occurrence in re.finditer("pix", page, re.IGNORECASE):
        near_pix = page[max(0, occurrence.start() - 100) : occurrence.start() + 240]
        try:
            rates = [
                percentage_basis_points(value.replace(",", "."))
                for value in _PERCENT.findall(near_pix)
            ]
        except ValueError as error:
            raise ValidationError("invalid PIX percentage in policy PDF") from error
        if basis_points in rates:
            return True
    return False


def _validate_passages(passages: object, pages: list[str]) -> list[dict[str, object]]:
    _check_passage_collection(passages)
    assert isinstance(passages, list)
    result = [_passage_record(item, pages) for item in passages]
    _check_unique_passages(result)
    _check_page_coverage(result, pages)
    return result


def _check_passage_collection(passages):
    if not isinstance(passages, list) or not passages or len(passages) > 200:
        raise ValidationError("review at least one policy passage")


def _check_unique_passages(passages):
    keys = {(item["page"], item["section"], item["text"]) for item in passages}
    if len(keys) != len(passages):
        raise ValidationError("duplicate policy passage")


def _check_page_coverage(passages, pages):
    covered = {item["page"] for item in passages}
    if covered != set(range(1, len(pages) + 1)):
        raise ValidationError("review every policy PDF page before publication")


def _passage_record(value: object, pages: list[str]) -> dict[str, object]:
    item = value if isinstance(value, dict) else {}
    if set(item) != _PASSAGE_FIELDS:
        raise ValidationError("invalid policy passage fields")
    page, section, topic = item["page"], item["section"], item["topic"]
    audience, conflict, text = item["audience"], item["conflict"], item["text"]
    _validate_passage_fields(page, section, topic, audience, conflict, text, pages)
    assert isinstance(page, int) and isinstance(section, str) and isinstance(topic, str)
    assert isinstance(audience, str) and isinstance(conflict, bool) and isinstance(text, str)
    return {
        "id": hashlib.sha256(f"{page}:{section}:{text}".encode()).hexdigest()[:16],
        "page": page,
        "section": section.strip(),
        "topic": normalize_text(topic),
        "audience": audience,
        "conflict": conflict,
        "text": " ".join(text.split()),
    }


def _validate_passage_fields(page, section, topic, audience, conflict, text, pages):
    _validate_locator(page, section, topic, pages)
    _validate_audience(audience, conflict)
    _validate_text(text, page, pages)


def _validate_locator(page, section, topic, pages):
    if type(page) is not int or not 1 <= page <= len(pages):
        raise ValidationError("invalid policy passage page")
    if not _valid_locator(section, topic):
        raise ValidationError("policy passage locator and topic are required")


def _valid_locator(section, topic):
    return (
        isinstance(section, str)
        and bool(section.strip())
        and isinstance(topic, str)
        and topic in TOPICS
    )


def _validate_audience(audience, conflict):
    if not _valid_audience(audience):
        raise ValidationError("invalid policy audience")
    if type(conflict) is not bool:
        raise ValidationError("invalid policy conflict marker")


def _valid_audience(audience):
    return isinstance(audience, str) and audience in {"public", "internal", "application-only"}


def _validate_text(text, page, pages):
    if not _valid_passage_text(text):
        raise ValidationError("policy passage must contain at most 400 characters")
    normalized = normalize_text(text)
    if not normalized or normalized not in normalize_text(pages[page - 1]):
        raise ValidationError("policy passage text is not present on the selected page")


def _valid_passage_text(text):
    return isinstance(text, str) and bool(text.strip()) and len(text) <= 400
