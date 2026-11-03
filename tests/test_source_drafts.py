import hashlib, tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.test import TestCase, override_settings

from emporio.catalog.models import Product, SourceAuditEvent, SourceSnapshot
from tests.source_csv_fixtures import copy_sources


class SourceDraftTests(TestCase):
    def setUp(self):
        from emporio.sources.drafts import create_draft

        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.bundle_root = Path(self.temp.name) / "bundles"; self.sources = copy_sources(self)
        self.settings = override_settings(EMPORIO_BUNDLE_ROOT=str(self.bundle_root))
        self.settings.enable(); self.addCleanup(self.settings.disable)
        self.user = get_user_model().objects.create_user(username="maintainer", password="pw", is_staff=True)
        call_command("load_sources", source_dir=str(self.sources), verbosity=0)
        self.product_id = Product.objects.filter(snapshot__is_active=True).order_by("source_id").first().source_id
        product_type = ContentType.objects.get_for_model(Product)
        self.user.user_permissions.add(*[
            Permission.objects.get_or_create(content_type=product_type, codename=code, defaults={"name": code})[0]
            for code in ("view_product", "change_product")
        ])
        self.draft = create_draft(self.user)

    def test_draft_persists_and_staged_cell_is_not_active_until_publish(self):
        from emporio.sources.drafts import preview_draft, stage_cell

        stage_cell(self.user, self.draft, "products", self.product_id, "name", "Draft name", expected_revision=0)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.revision, 1)
        self.assertEqual(preview_draft(self.user, self.draft)["products"][0]["name"], "Draft name")
        self.assertEqual(SourceSnapshot.objects.get(is_active=True).version, self.draft.base_version)

    def test_source_permission_is_enforced(self):
        from emporio.sources.drafts import stage_cell

        stranger = get_user_model().objects.create_user(username="stranger")
        with self.assertRaises(PermissionDenied):
            stage_cell(stranger, self.draft, "products", self.product_id, "name", "No", expected_revision=0)

    def test_stale_revision_conflicts_and_publish_requires_permission(self):
        from emporio.sources.drafts import preview_draft, publish_draft, stage_cell

        with self.assertRaises(Exception):
            stage_cell(self.user, self.draft, "products", self.product_id, "name", "One", expected_revision=1)
        with self.assertRaises(PermissionDenied):
            publish_draft(self.user, self.draft, expected_revision=0)

    def test_publish_creates_snapshot_and_bundle_files_match(self):
        from emporio.sources.drafts import preview_draft, publish_draft, stage_cell

        permission = Permission.objects.create(
            content_type=ContentType.objects.get_for_model(SourceSnapshot),
            codename="publish_sources", name="Can publish sources",
        )
        self.user.user_permissions.add(permission)
        stage_cell(self.user, self.draft, "products", self.product_id, "name", "Published name", expected_revision=0)
        preview_draft(self.user, self.draft)
        self.assertTrue(SourceAuditEvent.objects.filter(draft=self.draft, event="previewed", revision=1).exists())
        snapshot = publish_draft(self.user, self.draft, expected_revision=1)
        self.assertTrue(snapshot.is_active)
        bundle = self.bundle_root / snapshot.version
        self.assertTrue(bundle.is_dir())
        base = self.bundle_root / self.draft.base_version
        hashes = snapshot.manifest["csv_sha256"]
        for path in bundle.iterdir():
            key = path.stem.rsplit(" - ", 1)[-1]
            expected = snapshot.manifest["pdf_sha256"] if path.suffix == ".pdf" else hashes[key]
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), expected)
            if path.name != "desafio_tecnico_ai_eng - products.csv":
                self.assertEqual(path.read_bytes(), (base / path.name).read_bytes())
        self.assertIn(b"Published name", (bundle / "desafio_tecnico_ai_eng - products.csv").read_bytes())
