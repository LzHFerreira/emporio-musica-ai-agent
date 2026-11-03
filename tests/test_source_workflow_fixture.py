import csv
import io
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.management import call_command
from django.test import Client, TestCase, override_settings

from emporio.catalog.models import Product, SourceSnapshot
from emporio.sources.read import CSV_FILES, CSV_HEADERS
from tests.source_csv_fixtures import copy_sources


class SourceWorkflowFixture(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.bundle_root = Path(self.temp.name) / "bundles"
        self.sources = copy_sources(self)
        self.settings_override = override_settings(EMPORIO_BUNDLE_ROOT=str(self.bundle_root))
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        call_command("load_sources", source_dir=str(self.sources), verbosity=0)
        self.snapshot = SourceSnapshot.objects.get(is_active=True)
        self.product = Product.objects.filter(snapshot=self.snapshot).order_by("source_id").first()
        self.user = get_user_model().objects.create_user(
            "workflow", password="secret", is_staff=True
        )
        self.client = Client(enforce_csrf_checks=True)

    def grant(self, *codes, user=None):
        user = user or self.user
        content_type = ContentType.objects.get_for_model(SourceSnapshot)
        user.user_permissions.add(
            *[
                Permission.objects.get_or_create(
                    content_type=content_type, codename=code, defaults={"name": code}
                )[0]
                for code in codes
            ]
        )

    def login(self, user=None):
        user = user or self.user
        self.assertTrue(self.client.login(username=user.username, password="secret"))

    def post_csrf(self, url, data):
        return self.client.post(url, data, HTTP_X_CSRFTOKEN=self.client.cookies["csrftoken"].value)

    def unavailable_product_ids(self):
        ordered = csv_rows(self.sources / CSV_FILES["order_items"], "product_id")
        promoted = csv_rows(self.sources / CSV_FILES["promotions"], "product_id")
        return ordered | promoted

    def safe_product(self, rows):
        unavailable = self.unavailable_product_ids()
        return next(row for row in rows if row["product_id"] not in unavailable)

    def replacement_product_csv(self, rows):
        removable = self.safe_product(rows)["product_id"]
        replacement = [row for row in rows if row["product_id"] != removable]
        stream = io.StringIO()
        writer = csv.DictWriter(stream, fieldnames=CSV_HEADERS["products"])
        writer.writeheader()
        writer.writerows(replacement)
        stream.seek(0)
        return stream

    def staged_removal_draft(self):
        from emporio.sources.drafts import create_draft, preview_draft, stage_upload

        self.grant(
            "view_products",
            "edit_products",
            "publish_products",
            "delete_products",
            "rollback_sources",
        )
        draft = create_draft(self.user)
        with (self.sources / CSV_FILES["products"]).open(encoding="utf-8-sig") as stream:
            rows = list(csv.DictReader(stream))
        draft = stage_upload(
            self.user,
            draft,
            "products",
            self.replacement_product_csv(rows),
            mode="replace",
            expected_revision=0,
        )
        preview_draft(self.user, draft)
        return draft


def csv_rows(path, field):
    """Read one identifier column from a canonical CSV source."""
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return {row[field] for row in csv.DictReader(stream)}


def workflow_request(factory, user, method, path, data=None):
    """Build a request with staff identity and an initialized session."""
    request = getattr(factory, method)(path, data or {})
    request.user = user
    SessionMiddleware(lambda req: None).process_request(request)
    request.session.save()
    return request
