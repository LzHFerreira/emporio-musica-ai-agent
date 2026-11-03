"""Shared authenticated web fixture for protected source-view tests."""

import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.test import Client, TestCase, override_settings

from emporio.catalog.models import Product, SourceSnapshot
from tests.source_csv_fixtures import copy_sources


class StaffSourceWebFixture(TestCase):
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
        self.user = get_user_model().objects.create_user("staff", password="secret", is_staff=True)
        self.client = Client(enforce_csrf_checks=True)

    def grant(self, *codenames):
        content_type = ContentType.objects.get_for_model(SourceSnapshot)
        permissions = [
            Permission.objects.get_or_create(
                content_type=content_type, codename=code, defaults={"name": code}
            )[0]
            for code in codenames
        ]
        self.user.user_permissions.add(*permissions)

    def login(self):
        self.assertTrue(self.client.login(username="staff", password="secret"))

    def post_with_csrf(self, path, data):
        token = self.client.cookies["csrftoken"].value
        return self.client.post(path, data, HTTP_X_CSRFTOKEN=token)
