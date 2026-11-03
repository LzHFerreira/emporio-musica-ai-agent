"""Reusable policy PDF draft and publication helpers."""

import json

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from emporio.catalog.models import Product, SourceSnapshot
from emporio.policy import lookup_public_policy
from tests.policy_pdf_fixture import text_pdf
from tests.test_source_workflow_fixture import SourceWorkflowFixture


class PolicySourceWorkflowBase(SourceWorkflowFixture):
    def setUp(self):
        super().setUp()
        self.login()
        self.grant("view_policy_pdf", "edit_policy_pdf", "publish_policy_pdf", "publish_sources", "rollback_sources")
        self.upload_url = reverse("staff-source-upload", args=["policy_pdf"])
        self.original = self.snapshot

    def pdf(self, percentage):
        return text_pdf([
            "Hours Monday to Friday 09:00-18:00",
            f"Payment PIX discount {percentage} percent of table price",
            "Internal: ask management before policy application",
        ])

    def passage(self, section, topic, audience, text):
        return {"page": 1, "section": section, "topic": topic, "audience": audience, "conflict": False, "text": text}

    def reviews(self, percentage):
        passages = [
            self.passage("§2", "hours", "public", "Hours Monday to Friday 09:00-18:00"),
            self.passage("§3", "payment", "public", f"Payment PIX discount {percentage} percent of table price"),
            self.passage("§7.1", "internal", "internal", "Internal: ask management before policy application"),
        ]
        return {
            "revision": 1,
            "pix_discount_percent": str(percentage),
            "unchanged_rules_attested": "yes",
            "passage_reviews": json.dumps(passages),
        }

    def upload_pdf(self, content):
        self.client.cookies["csrftoken"] = "a" * 32
        self.client.get(self.upload_url)
        upload = SimpleUploadedFile("policy.pdf", content, content_type="application/pdf")
        revision = self.client.session.get("source_draft_revision", 0)
        return self.post_csrf(self.upload_url, {"file": upload, "revision": revision})

    def review_pdf(self, draft, percentage):
        preview_url = reverse("staff-source-preview", args=[draft.pk])
        preview = self.client.get(preview_url)
        self.assertContains(preview, f"Payment PIX discount {percentage} percent")
        response = self.post_csrf(preview_url, self.reviews(percentage))
        self.assertEqual(response.status_code, 200)
        draft.refresh_from_db()

    def assert_unreviewed_publish_blocked(self, draft):
        path = reverse("staff-source-publish", args=[draft.pk])
        response = self.post_csrf(path, {"revision": draft.revision})
        self.assertEqual(response.status_code, 400)
        active = SourceSnapshot.objects.get(is_active=True)
        self.assertEqual(active.version, self.original.version)


class PolicyPublicationHelpers:
    def publish_pdf(self, draft):
        path = reverse("staff-source-publish", args=[draft.pk])
        response = self.post_csrf(path, {"revision": draft.revision})
        self.assertEqual(response.status_code, 302)
        active = SourceSnapshot.objects.get(is_active=True)
        self.assertEqual(active.pix_basis_points, 300)
        self.assertEqual(Product.objects.get(snapshot=active, source_id=101).pix_payable_cents, 101753)
        return active

    def assert_policy_results(self, active):
        result = lookup_public_policy(query="horario de funcionamento", topic="hours")
        self.assertIn("09:00-18:00", result["data"][0]["text"])
        self.assertEqual(result["sources"][0]["bundle_version"], active.version)
        self.assertEqual(lookup_public_policy(query="management policy application")["data"], [])

    def rollback_pdf(self, active):
        path = reverse("staff-source-rollback", args=[self.original.version])
        data = {"reason": "Restaurar política", "expected_version": active.version}
        self.assertEqual(self.post_csrf(path, data).status_code, 302)
        self.original.refresh_from_db()
        self.assertTrue(self.original.is_active)
        self.assertEqual(self.original.pix_basis_points, 500)
        old = Product.objects.get(snapshot=self.original, source_id=101)
        self.assertEqual(old.pix_payable_cents, 99655)
        self.assertEqual(lookup_public_policy(query="horário", topic="hours")["sources"][0]["bundle_version"], self.original.version)
