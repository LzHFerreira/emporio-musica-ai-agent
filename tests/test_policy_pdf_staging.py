from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from emporio.sources import policy_pdf, policy_pdf_service, policy_pdf_staging
from emporio.sources.drafts import create_draft
from tests.policy_pdf_fixture import text_pdf
from tests.policy_pdf_test_support import PolicyPdfTestSupport


class PolicyPdfStagingTests(PolicyPdfTestSupport):
    def test_staging_rejects_stale_revision(self):
        with self.assertRaises(ValidationError):
            policy_pdf.stage_policy_pdf(
                self.user,
                self.draft,
                SimpleUploadedFile("policy.pdf", text_pdf(["PIX 5 percent"])),
                expected_revision=5,
            )

    def test_staging_root_rejects_storage_inside_static_root(self):
        static = Path(self.temp.name) / "static"
        for root in (static, static / "bundles"):
            with override_settings(EMPORIO_BUNDLE_ROOT=str(root), STATIC_ROOT=str(static)):
                with self.assertRaises(ValidationError):
                    policy_pdf_staging._staging_root()

    def test_staging_rejects_non_author_and_unsafe_candidate_path(self):
        another = self.user.__class__.objects.create_user("other-staff", is_staff=True)
        self.grant("edit_policy_pdf", user=another)
        upload = SimpleUploadedFile("policy.pdf", text_pdf(["PIX 5 percent"]))
        with self.assertRaises(PermissionDenied):
            policy_pdf.stage_policy_pdf(another, self.draft, upload, expected_revision=0)
        with patch.object(policy_pdf_staging, "uuid4", return_value=SimpleNamespace(hex="x/../../out")):
            with self.assertRaises(ValidationError):
                policy_pdf.stage_policy_pdf(
                    self.user,
                    self.draft,
                    SimpleUploadedFile("policy.pdf", text_pdf(["PIX 5 percent"])),
                    expected_revision=0,
                )

    def test_candidate_path_rejects_escape_and_missing_file(self):
        self.stage_pdf()
        path = policy_pdf_staging.candidate_path(self.draft.policy)
        self.assertTrue(path.is_file())
        with self.assertRaises(ValidationError):
            policy_pdf_staging.candidate_path({"candidate_path": "../../outside.pdf"})
        path.unlink()
        with self.assertRaises(ValidationError):
            policy_pdf_staging.candidate_path(self.draft.policy)

    def test_failed_persistence_removes_candidate_file(self):
        empty = create_draft(self.user)
        with patch.object(policy_pdf_service.SourceDraft.objects, "select_for_update", side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                policy_pdf.stage_policy_pdf(
                    self.user,
                    empty,
                    SimpleUploadedFile("policy.pdf", text_pdf(["PIX 5 percent"])),
                    expected_revision=empty.revision,
                )
        self.assertFalse(list(policy_pdf_staging._staging_root().glob(f"{empty.pk}-*.pdf")))
