import csv
import io
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings

from emporio.catalog.models import Product, SourceAuditEvent, SourceSnapshot
from emporio.sources.read import CSV_HEADERS
from tests.source_csv_fixtures import copy_sources, source_file


class SourceBulkOperations:
    def source_rows(self, source):
        with source_file(self.sources, source).open(encoding="utf-8-sig", newline="") as stream:
            return list(csv.DictReader(stream))

    def source_ids(self, source, field):
        return {row[field] for row in self.source_rows(source)}

    def replacement_rows(self, rows):
        unavailable = self.source_ids("order_items", "product_id")
        unavailable.update(self.source_ids("promotions", "product_id"))
        removable = next(row for row in rows if row["product_id"] not in unavailable)
        return [row for row in rows if row["product_id"] != removable["product_id"]]

    def upserted_products(self):
        from emporio.sources.drafts import preview_draft, stage_upload

        self.grant(self.user, "edit_products", "publish_products")
        before = preview_draft(self.user, self.draft)["products"]
        updated = dict(before[0], name="Updated")
        draft = stage_upload(
            self.user,
            self.draft,
            "products",
            self.upload([updated]),
            mode="upsert",
            expected_revision=0,
        )
        return draft, before, updated, preview_draft(self.user, draft)["products"]

    def stage_replacement(self, draft, after):
        from emporio.sources.drafts import stage_upload

        replacement = self.replacement_rows(after)
        with self.assertRaises(PermissionDenied):
            stage_upload(
                self.user,
                draft,
                "products",
                self.upload(replacement),
                mode="replace",
                expected_revision=draft.revision,
            )
        self.grant(self.user, "delete_products")
        return stage_upload(
            self.user,
            draft,
            "products",
            self.upload(replacement),
            mode="replace",
            expected_revision=draft.revision,
        )

    def confirm_replacement(self, replacement_draft, after):
        from emporio.sources.drafts import preview_draft, publish_draft

        self.assertEqual(
            len(preview_draft(self.user, replacement_draft)["products"]), len(after) - 1
        )
        with self.assertRaises(ValidationError):
            publish_draft(
                self.user, replacement_draft, expected_revision=replacement_draft.revision
            )
        published = publish_draft(
            self.user,
            replacement_draft,
            expected_revision=replacement_draft.revision,
            confirm_deletions=True,
        )
        self.assertTrue(published.is_active)
        self.assertEqual(Product.objects.filter(snapshot=published).count(), len(after) - 1)

    def published_price_change(self):
        from emporio.sources.drafts import preview_draft, publish_draft, stage_cell

        original = SourceSnapshot.objects.get(is_active=True)
        product = Product.objects.get(snapshot=original, source_id=self.product_id)
        prices = (product.base_cents, product.standard_payable_cents, product.pix_payable_cents)
        self.grant(self.user, "edit_products", "publish_products")
        stage_cell(
            self.user,
            self.draft,
            "products",
            self.product_id,
            "price_brl",
            "1500.00",
            expected_revision=0,
        )
        preview_draft(self.user, self.draft)
        self.assertTrue(
            SourceAuditEvent.objects.filter(
                draft=self.draft, event="previewed", revision=1
            ).exists()
        )
        changed = publish_draft(self.user, self.draft, expected_revision=1)
        return original, product, prices, changed


class SourceBulkFixture(SourceBulkOperations, TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self._configure_storage()
        self._load_baseline()

    def _configure_storage(self):
        self.bundle_root = Path(self.temp.name) / "bundles"
        self.sources = copy_sources(self)
        self.settings_override = override_settings(EMPORIO_BUNDLE_ROOT=str(self.bundle_root))
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

    def _load_baseline(self):
        call_command("load_sources", source_dir=str(self.sources), verbosity=0)
        self.product_id = (
            Product.objects.filter(snapshot__is_active=True).order_by("source_id").first().source_id
        )
        self.user = get_user_model().objects.create_user(
            username="maintainer", password="pw", is_staff=True
        )
        product_type = ContentType.objects.get_for_model(Product)
        permissions = [
            Permission.objects.get_or_create(
                content_type=product_type, codename=code, defaults={"name": code}
            )[0]
            for code in ("view_product", "change_product")
        ]
        self.user.user_permissions.add(*permissions)
        from emporio.sources.drafts import create_draft

        self.draft = create_draft(self.user)

    def grant(self, user, *codenames):
        content_type = ContentType.objects.get_for_model(SourceSnapshot)
        permissions = [
            Permission.objects.get_or_create(
                content_type=content_type, codename=name, defaults={"name": name}
            )[0]
            for name in codenames
        ]
        user.user_permissions.add(*permissions)

    def upload(self, rows, source="products"):
        stream = io.StringIO()
        writer = csv.DictWriter(stream, fieldnames=CSV_HEADERS[source])
        writer.writeheader()
        writer.writerows(rows)
        stream.seek(0)
        return stream
