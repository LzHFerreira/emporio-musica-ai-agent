"""Subprocess entrypoints used to kill publication at durable boundaries."""

import json
import os
import sys
from pathlib import Path


def _django():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "emporio.settings")
    import django

    django.setup()


def _grant(user, snapshot):
    from django.contrib.auth.models import Permission
    from django.contrib.contenttypes.models import ContentType

    content_type = ContentType.objects.get_for_model(snapshot)
    for code in ("view_products", "edit_products", "publish_products"):
        permission, _ = Permission.objects.get_or_create(
            content_type=content_type, codename=code, defaults={"name": code}
        )
        user.user_permissions.add(permission)


def _draft(user, snapshot):
    from emporio.catalog.models import Product
    from emporio.sources.drafts import create_draft, preview_draft, stage_cell

    product = Product.objects.filter(snapshot=snapshot).first()
    draft = create_draft(user)
    stage_cell(user, draft, "products", product.source_id, "name", "After restart", expected_revision=0)
    preview_draft(user, draft)
    return draft


def _kill_at(phase):
    from emporio.sources import draft_publication

    if phase == "after_commit":
        original = draft_publication._activate_reviewed

        def committed_then_exit(*args):
            result = original(*args)
            os._exit(72)

        draft_publication._activate_reviewed = committed_then_exit
        return
    original = draft_publication._activate

    def activation_then_exit(*args):
        if phase == "before_activation":
            os._exit(71)
        original(*args)
        os._exit(73)

    draft_publication._activate = activation_then_exit


def publish(source_dir, bundle_root, phase):
    _django()
    from django.contrib.auth import get_user_model
    from django.core.management import call_command
    from django.test.utils import override_settings
    from emporio.catalog.models import SourceSnapshot
    from emporio.sources.drafts import publish_draft

    settings = {"EMPORIO_BUNDLE_ROOT": bundle_root, "STATIC_ROOT": str(Path(bundle_root) / "static")}
    with override_settings(**settings):
        call_command("migrate", verbosity=0)
        call_command("load_sources", source_dir=source_dir, verbosity=0)
        snapshot = SourceSnapshot.objects.get(is_active=True)
        user = get_user_model().objects.create_user("crash", is_staff=True)
        _grant(user, snapshot)
        draft = _draft(user, snapshot)
        _kill_at(phase)
        publish_draft(user, draft, expected_revision=1)


def _inspection():
    from emporio.catalog.models import Product, SourceAuditEvent, SourceSnapshot
    from emporio.policy import lookup_public_policy

    active = SourceSnapshot.objects.get(is_active=True)
    product = Product.objects.filter(snapshot=active, name="After restart").first()
    policy = lookup_public_policy(query="horário", topic="hours", snapshot_version=active.version)
    return {
        "active": active.version,
        "active_count": SourceSnapshot.objects.filter(is_active=True).count(),
        "snapshots": list(SourceSnapshot.objects.order_by("created_at").values_list("version", "is_active")),
        "name": product.name if product else None,
        "product_prices_valid": _prices_valid(product),
        "published": _published_versions(SourceAuditEvent),
        "all_bundles_valid": _all_bundles_valid(SourceSnapshot),
        "has_inactive_snapshot": SourceSnapshot.objects.filter(is_active=False).exists(),
        "policy_version": policy["sources"][0]["bundle_version"] if policy["sources"] else None,
        "policy_outcome": policy["outcome"],
    }


def _prices_valid(product):
    return bool(product and product.base_cents > 0 and product.pix_payable_cents > 0)


def _published_versions(audit_model):
    return list(audit_model.objects.filter(event="published").values_list("target_version", flat=True))


def _all_bundles_valid(snapshot_model):
    from emporio.sources.bundle_storage import _bundle_matches, _expected_bundle_hashes

    root = Path(os.environ["EMPORIO_BUNDLE_ROOT"])
    return all(
        _bundle_matches(root / item.version, _expected_bundle_hashes(item.manifest))
        for item in snapshot_model.objects.all()
    )


def inspect():
    _django()
    from django.test.utils import override_settings

    with override_settings(EMPORIO_BUNDLE_ROOT=os.environ["EMPORIO_BUNDLE_ROOT"]):
        print(json.dumps(_inspection()))


if __name__ == "__main__":
    publish(*sys.argv[2:]) if sys.argv[1] == "publish" else inspect()
