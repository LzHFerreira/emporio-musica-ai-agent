"""Validate and durably stage complete managed CSV bundles for drafts."""

import csv
import hashlib
import json
import shutil
import tempfile
from decimal import Decimal
from pathlib import Path

from django.conf import settings

from emporio.sources.policy_pdf_staging import candidate_path
from emporio.sources.publish import _pricing_rule, _retain_bundle
from emporio.sources.read import CSV_FILES, CSV_HEADERS
from emporio.sources.validate import validate_sources


def prepare_bundle(sources, changed, base, policy=None):
    """Validate all six datasets and retain changed plus copied base files."""
    rows = validate_sources(sources)
    root = Path(
        getattr(settings, "EMPORIO_BUNDLE_ROOT", Path(settings.BASE_DIR) / ".source-bundles")
    )
    rule, pix = _base_rule(base)
    with tempfile.TemporaryDirectory(prefix="source-draft-") as directory:
        source_dir = Path(directory)
        _write_csvs(source_dir, root / base.version, sources, changed)
        policy_manifest = _stage_policy(
            source_dir, root / base.version, changed, policy, base.manifest.get("policy", {})
        )
        if "policy_pdf" in changed:
            pricing = policy_manifest.get("pricing_rule")
            if not isinstance(pricing, dict):
                raise ValueError("policy PDF pricing rule is missing")
            pix = int(pricing["pix_basis_points"])
            rule = _rule_name(pix)
        manifest = _manifest(source_dir, rule, pix, policy_manifest)
        version = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
        _retain_bundle(source_dir, version, manifest)
    return rows, manifest, version


def _write_csvs(source_dir, base_dir, sources, changed):
    for name, filename in CSV_FILES.items():
        target = source_dir / filename
        if name not in changed:
            shutil.copyfile(base_dir / filename, target)
            continue
        with target.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=CSV_HEADERS[name])
            writer.writeheader()
            writer.writerows(sources[name])


def _base_rule(base):
    policy = base.manifest.get("policy", {})
    pricing = policy.get("pricing_rule", {})
    if pricing.get("code") == "pix-full-payment-discount-v1":
        points = int(pricing.get("pix_basis_points", base.pix_basis_points))
        return base.pricing_rule_version, points
    return _pricing_rule()


def _rule_name(basis_points):
    amount = format(Decimal(basis_points) / Decimal(100), "f").rstrip("0").rstrip(".")
    amount = amount or "0"
    return f"pix-{amount}-v1"


def _stage_policy(source_dir, base_dir, changed, policy, base_policy):
    if "policy_pdf" not in changed:
        return _copy_base_policy(source_dir, base_dir, base_policy)
    return _stage_replacement_policy(source_dir, policy)


def _copy_base_policy(source_dir, base_dir, base_policy):
    shutil.copyfile(base_dir / "políticas_da_loja.pdf", source_dir / "políticas_da_loja.pdf")
    return base_policy


def _stage_replacement_policy(source_dir, policy):
    if not policy or not policy.get("review"):
        raise ValueError("policy PDF replacement requires review")
    target = candidate_path(policy)
    content = target.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    _check_review_hash(policy, digest)
    (source_dir / "políticas_da_loja.pdf").write_bytes(content)
    return {
        "pdf_sha256": digest,
        "page_count": policy.get("page_count", len(policy.get("pages", []))),
        "extractor_version": "pypdfium2-text-v1",
        "review_version": "staff-passage-review-v1",
        "pricing_rule": policy["review"]["pricing_rule"],
        "passages": policy["review"]["passages"],
    }


def _check_review_hash(policy, digest):
    if digest != policy.get("candidate_sha256") or digest != policy["review"].get("pdf_sha256"):
        raise ValueError("policy PDF review hash is stale")


def _manifest(source_dir, rule, pix, policy):
    hashes = {
        name: hashlib.sha256((source_dir / filename).read_bytes()).hexdigest()
        for name, filename in CSV_FILES.items()
    }
    pdf_hash = hashlib.sha256((source_dir / "políticas_da_loja.pdf").read_bytes()).hexdigest()
    return {
        "csv_sha256": hashes,
        "pdf_sha256": pdf_hash,
        "pricing_rule_version": rule,
        "pix_basis_points": pix,
        "managed_publication": True,
        "policy": policy,
        "policy_rule_code": policy.get("pricing_rule", {}).get("code", ""),
    }
