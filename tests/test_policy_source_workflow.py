from django.urls import reverse

from emporio.catalog.models import SourceSnapshot
from tests.policy_source_workflow_fixture import PolicyPublicationHelpers, PolicySourceWorkflowBase


class PolicyApprovalInvalidationTests(PolicySourceWorkflowBase):
    def test_review_approval_is_invalidated_when_candidate_pdf_hash_changes(self):
        staged = self.upload_pdf(self.pdf(3))
        self.assertEqual(staged.status_code, 200)
        draft = staged.context["draft"]
        self.post_csrf(reverse("staff-source-preview", args=[draft.pk]), self.reviews(3))
        changed = self.upload_pdf(self.pdf(4))
        self.assertEqual(changed.status_code, 200)
        draft.refresh_from_db()
        path = reverse("staff-source-publish", args=[draft.pk])
        self.assertEqual(self.post_csrf(path, {"revision": draft.revision}).status_code, 400)
        self.assertEqual(SourceSnapshot.objects.get(is_active=True).version, self.original.version)


class PolicyPublishRollbackTests(PolicySourceWorkflowBase, PolicyPublicationHelpers):
    def test_reviewed_rule_passages_prices_and_rollback_publish_together(self):
        staged = self.upload_pdf(self.pdf(3))
        self.assertEqual(staged.status_code, 200)
        draft = staged.context["draft"]
        self.assert_unreviewed_publish_blocked(draft)
        self.review_pdf(draft, 3)
        active = self.publish_pdf(draft)
        self.assert_policy_results(active)
        self.rollback_pdf(active)


class PolicyPdfBoundTests(PolicySourceWorkflowBase):
    def test_pdf_rejects_more_than_twenty_pages(self):
        from tests.policy_pdf_fixture import text_pdf

        self.assertEqual(self.upload_pdf(text_pdf(["Policy page"], pages=21)).status_code, 400)

    def test_pdf_rejects_more_than_128_kibibytes_of_extracted_text(self):
        from tests.policy_pdf_fixture import text_pdf

        content = text_pdf(["A" * (128 * 1024 + 1)])
        self.assertEqual(self.upload_pdf(content).status_code, 400)
