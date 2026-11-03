"""Reviewed passage map for the one approved initial policy fixture."""

import hashlib

from django.core.exceptions import ValidationError

from emporio.sources.policy_fixture_text import (
    _initial_section as _initial_section,
)
from emporio.sources.policy_fixture_text import (
    extract_fixture_passages,
)
from emporio.sources.policy_pdf_review import RULE_CODE

INITIAL_PDF_SHA256 = "b7527f96896929f4ba929de117651c6717e25b7a3b92b34bc54d5ba32f6156f7"


def initial_policy_manifest(
    content: bytes, pages: list[str], basis_points: int
) -> dict[str, object]:
    """Seed only the exact source-reviewed fixture and bind its passages to its hash."""
    digest = hashlib.sha256(content).hexdigest()
    if digest != INITIAL_PDF_SHA256:
        raise ValidationError("a new policy PDF must be reviewed through staff source maintenance")
    passages = extract_fixture_passages(pages)
    if not passages:
        raise ValidationError("policy PDF has no reviewed public passages")
    return {
        "pdf_sha256": digest,
        "page_count": len(pages),
        "extractor_version": "ghostscript-txtwrite-v1",
        "review_version": "initial-passage-map-v1",
        "pricing_rule": {"code": RULE_CODE, "pix_basis_points": basis_points},
        "passages": passages,
    }
