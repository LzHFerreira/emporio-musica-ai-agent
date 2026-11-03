from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from emporio.catalog.models import SourceSnapshot
from tests.staff_source_web_fixture import StaffSourceWebFixture


class StaffPolicyPdfWebTests(StaffSourceWebFixture):
    def setUp(self):
        super().setUp()
        self.login()
        self.endpoint = reverse("staff-source-upload", args=["policy_pdf"])

    def prime_csrf(self):
        self.client.cookies["csrftoken"] = "a" * 32
        self.client.get(self.endpoint)

    def test_pdf_upload_is_exposed_to_authorized_staff(self):
        self.grant("view_policy_pdf", "edit_policy_pdf")
        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PDF")

    def test_valid_pdf_upload_stages_without_activating_the_snapshot(self):
        self.grant("view_policy_pdf", "edit_policy_pdf", "publish_policy_pdf")
        self.prime_csrf()
        content = (self.sources / "políticas_da_loja.pdf").read_bytes() + b"\n% revision"
        upload = SimpleUploadedFile("policy.pdf", content, content_type="application/pdf")
        response = self.post_with_csrf(self.endpoint, {"file": upload, "revision": 0})
        self.assertEqual(response.status_code, 200)
        active = SourceSnapshot.objects.get(is_active=True)
        self.assertEqual(active.version, self.snapshot.version)

    def test_pdf_upload_enforces_the_ten_megabyte_limit(self):
        self.grant("view_policy_pdf", "edit_policy_pdf")
        self.prime_csrf()
        content = b"%PDF-" + b"x" * (10 * 1024 * 1024)
        upload = SimpleUploadedFile("large.pdf", content, content_type="application/pdf")
        response = self.post_with_csrf(self.endpoint, {"file": upload, "revision": 0})
        self.assertEqual(response.status_code, 400)
