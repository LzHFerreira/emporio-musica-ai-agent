"""Stage and activate versioned SQLite source snapshots."""

import hashlib
import json

from django.db import IntegrityError, transaction

from emporio.catalog.models import SourceSnapshot
from emporio.sources.publish_catalog import insert_catalog
from emporio.sources.publish_orders import insert_orders
from emporio.sources.read import SourceImportError


def _activate(version, manifest, rule, pix, rows):
    """Stage rows durably, then change the active snapshot pointer atomically."""
    _stage_snapshot(version, manifest, rule, pix, rows)
    return _activate_staged(version, manifest)


@transaction.atomic
def _activate_staged(version, manifest):
    active = SourceSnapshot.objects.select_for_update().filter(is_active=True).first()
    managed_active = active is not None and active.manifest.get("managed_publication") is True
    _check_managed_import(managed_active, manifest)
    current = SourceSnapshot.objects.get(version=version)
    if current.manifest != manifest:
        raise SourceImportError("snapshot version conflicts with its manifest")
    SourceSnapshot.objects.exclude(pk=current.pk).filter(is_active=True).update(is_active=False)
    if not current.is_active:
        current.is_active = True
        current.save(update_fields=["is_active"])
    return current


def _stage_snapshot(version, manifest, rule, pix, rows):
    if hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest() != version:
        raise SourceImportError("snapshot version does not match its manifest")
    existing = SourceSnapshot.objects.filter(version=version).first()
    if existing is not None:
        _verify_snapshot_identity(existing, manifest, rule, pix)
        return
    try:
        with transaction.atomic():
            snapshot = SourceSnapshot.objects.create(
                version=version,
                manifest=manifest,
                pricing_rule_version=rule,
                pix_basis_points=pix,
            )
            insert_catalog(snapshot, rows)
            insert_orders(snapshot, rows)
    except IntegrityError:
        snapshot = SourceSnapshot.objects.get(version=version)
        _verify_snapshot_identity(snapshot, manifest, rule, pix)


def _verify_snapshot_identity(snapshot, manifest, rule, pix):
    if (
        snapshot.manifest != manifest
        or snapshot.pricing_rule_version != rule
        or snapshot.pix_basis_points != pix
    ):
        raise SourceImportError("snapshot version conflicts with staged data")


def _check_managed_import(managed_active, manifest):
    if managed_active and manifest.get("managed_publication") is not True:
        raise SourceImportError("legacy source imports cannot replace a managed publication")


def _pricing_rule() -> tuple[str, int]:
    """Read validated, versioned reviewed pricing metadata from Django settings."""
    from django.conf import settings

    version = getattr(settings, "EMPORIO_PRICING_RULE_VERSION", "pix-500-v1")
    basis_points = getattr(settings, "EMPORIO_PIX_BASIS_POINTS", 500)
    if (
        not isinstance(version, str)
        or not version.strip()
        or type(basis_points) is not int
        or not 0 <= basis_points <= 10_000
    ):
        raise SourceImportError("invalid pricing rule settings")
    return version, basis_points
