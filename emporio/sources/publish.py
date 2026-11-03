"""Build and atomically activate a validated CSV-derived SQLite snapshot."""

import hashlib
import json
from pathlib import Path

from django.core.exceptions import ValidationError

from emporio.catalog.models import SourceSnapshot
from emporio.sources.bundle_storage import _retain_bundle
from emporio.sources.policy_pdf import RULE_CODE, extract_pdf_pages, initial_policy_manifest
from emporio.sources.publication_snapshot import (
    _activate as _activate,
)
from emporio.sources.publication_snapshot import (
    _pricing_rule as _pricing_rule,
)
from emporio.sources.publication_snapshot import (
    _stage_snapshot as _stage_snapshot,  # noqa: F401 - compatibility seam
)
from emporio.sources.read import SourceImportError, read_csv_sources
from emporio.sources.validate import validate_sources


def load_sources(source_dir: str) -> SourceSnapshot:
    """Validate six fixed CSVs, derive prices, and atomically activate a version."""
    _require_initial_import()
    raw, hashes = read_csv_sources(source_dir)
    rows = validate_sources(raw)
    source_root = Path(source_dir).resolve(strict=True)
    rule, pix = _pricing_rule()
    pdf_hash, policy = _initial_policy(source_root, pix)
    manifest = _build_manifest(hashes, rule, pix, pdf_hash, policy)
    version = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    _retain_bundle(source_root, version, manifest)
    return _activate(version, manifest, rule, pix, rows)


def _require_initial_import():
    if SourceSnapshot.objects.filter(is_active=True, manifest__managed_publication=True).exists():
        raise SourceImportError(
            "managed source bundles must be changed through the protected draft service"
        )


def _initial_policy(source_root, pix):
    pdf = (source_root / "políticas_da_loja.pdf").resolve(strict=True)
    if pdf.parent != source_root or pdf.stat().st_size > 10 * 1024 * 1024:
        raise SourceImportError("invalid source file: políticas_da_loja.pdf")
    pdf_content = pdf.read_bytes()
    try:
        policy_pages = extract_pdf_pages(pdf_content)
        policy = initial_policy_manifest(pdf_content, policy_pages, pix)
    except ValidationError as error:
        raise SourceImportError(str(error)) from error
    pdf_hash = hashlib.sha256(pdf_content).hexdigest()
    return pdf_hash, policy


def _build_manifest(hashes, rule, pix, pdf_hash, policy):
    return {
        "csv_sha256": hashes,
        "pdf_sha256": pdf_hash,
        "pricing_rule_version": rule,
        "pix_basis_points": pix,
        "policy": policy,
        "policy_rule_code": RULE_CODE,
    }
