"""Reactivate a retained, hash-verified source snapshot with an audit record."""

import hashlib
import re
from pathlib import Path

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from emporio.catalog.models import SourceAuditEvent, SourceSnapshot
from emporio.sources.draft_audit import record_rejected
from emporio.sources.draft_data import bundle, require, staff_user
from emporio.sources.publish import _pricing_rule
from emporio.sources.read import CSV_FILES, SourceImportError
from emporio.sources.validate import validate_sources


def rollback_sources(user, target_version, *, expected_version, reason):
    """Restore a retained snapshot only if active version and reviewed rules match."""
    try:
        return _rollback_sources(user, target_version, expected_version, reason)
    except (PermissionDenied, ValidationError, ValueError) as error:
        record_rejected(user, None, "", error)
        raise


def _rollback_sources(user, target_version, expected_version, reason):
    user = staff_user(user)
    if not user.has_perm("catalog.rollback_sources"):
        raise PermissionDenied("rollback permission required")
    reason = _reason(reason)
    active, target, changed = _inspect_rollback(target_version, expected_version)
    return _activate_rollback(user, target, expected_version, reason, changed)


def _inspect_rollback(target_version, expected_version):
    active = SourceSnapshot.objects.get(is_active=True)
    if active.version != expected_version:
        raise ValidationError("stale active source version")
    target = SourceSnapshot.objects.get(version=target_version)
    _check_rule_compatibility(target)
    active_sources, target_sources = bundle(active), bundle(target)
    _validate_rollback_rows(target_sources)
    changed = _changed_sources(active_sources, target_sources)
    if _policy_changed(active, target):
        changed.append("policy_pdf")
    return active, target, changed


def _changed_sources(active_sources, target_sources):
    return [name for name in CSV_FILES if active_sources[name] != target_sources[name]]


def _policy_changed(active, target):
    return active.manifest.get("pdf_sha256") != target.manifest.get(
        "pdf_sha256"
    ) or active.manifest.get("policy") != target.manifest.get("policy")


def _validate_rollback_rows(sources):
    try:
        validate_sources(sources)
    except (TypeError, ValueError, KeyError) as error:
        raise ValidationError(
            "rollback bundle is incompatible with current source schema"
        ) from error


def _activate_rollback(user, inspected_target, expected_version, reason, changed):
    with transaction.atomic():
        active = SourceSnapshot.objects.select_for_update().get(is_active=True)
        if active.version != expected_version:
            raise ValidationError("stale active source version")
        target = SourceSnapshot.objects.select_for_update().get(pk=inspected_target.pk)
        _check_target_unchanged(target, inspected_target)
        fresh = staff_user(user)
        _authorize_rollback(fresh, changed)
        _switch_snapshot(target)
        _record_rollback(fresh, active, target, changed, reason)
        return target


def _authorize_rollback(user, changed):
    if not user.has_perm("catalog.rollback_sources"):
        raise PermissionDenied("rollback permission required")
    for source in changed:
        require(user, "edit", source)
        require(user, "publish", source)


def _record_rollback(user, active, target, changed, reason):
    SourceAuditEvent.objects.create(
        actor=user,
        event="rolled_back",
        sources=changed,
        base_version=active.version,
        target_version=target.version,
        outcome="success",
        reason=reason,
        counts={"sources": len(changed)},
    )


def _check_target_unchanged(target, inspected):
    if (
        target.manifest != inspected.manifest
        or target.pricing_rule_version != inspected.pricing_rule_version
        or target.pix_basis_points != inspected.pix_basis_points
    ):
        raise ValidationError("rollback target changed during review")


def _switch_snapshot(target):
    SourceSnapshot.objects.exclude(pk=target.pk).filter(is_active=True).update(is_active=False)
    if not target.is_active:
        target.is_active = True
        target.save(update_fields=["is_active"])


def _reason(value):
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("rollback reason is required")
    return " ".join(value.split())[:500]


def _check_rule_compatibility(snapshot):
    try:
        rule, _ = _pricing_rule()
    except SourceImportError as error:
        raise ValidationError("current pricing rule is invalid") from error
    policy = snapshot.manifest.get("policy", {})
    supported = policy.get("pricing_rule", {}).get("code") == "pix-full-payment-discount-v1"
    version_pattern = r"pix-[0-9]+(?:\.[0-9]{1,2})?-v1"
    compatible_name = bool(re.fullmatch(version_pattern, snapshot.pricing_rule_version))
    current_supported = bool(re.fullmatch(r"pix-[0-9]+(?:\.[0-9]{1,2})?-v1", rule))
    if not supported or not compatible_name or not current_supported:
        raise ValidationError("rollback pricing rule is incompatible")
    _verify_bundle_files(snapshot)


def _verify_bundle_files(snapshot):
    root = Path(
        getattr(settings, "EMPORIO_BUNDLE_ROOT", Path(settings.BASE_DIR) / ".source-bundles")
    ).resolve()
    path = (root / snapshot.version).resolve()
    if path.parent != root or not path.is_dir():
        raise ValidationError("rollback bundle is unavailable")
    _verify_bundle_manifest(path, snapshot)


def _verify_bundle_manifest(path, snapshot):
    expected_hashes = snapshot.manifest.get("csv_sha256", {})
    expected_files = set(CSV_FILES.values()) | {"políticas_da_loja.pdf"}
    if (
        not isinstance(expected_hashes, dict)
        or {entry.name for entry in path.iterdir()} != expected_files
    ):
        raise ValidationError("rollback bundle failed hash verification")
    for source, filename in CSV_FILES.items():
        _verify_file(path, filename, expected_hashes.get(source))
    _verify_file(path, "políticas_da_loja.pdf", snapshot.manifest.get("pdf_sha256"))


def _verify_file(path, filename, expected):
    file_path = (path / filename).resolve()
    if file_path.parent != path:
        raise ValidationError("rollback bundle failed hash verification")
    actual = hashlib.sha256(file_path.read_bytes()).hexdigest() if file_path.is_file() else None
    if actual != expected:
        raise ValidationError("rollback bundle failed hash verification")
