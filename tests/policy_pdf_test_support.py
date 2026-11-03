"""Shared staff draft setup for policy PDF service tests."""

from django.core.files.uploadedfile import SimpleUploadedFile

from emporio.sources import policy_pdf
from emporio.sources.drafts import create_draft
from tests.policy_pdf_fixture import text_pdf
from tests.test_source_workflow_fixture import SourceWorkflowFixture


class PolicyPdfTestSupport(SourceWorkflowFixture):
    def setUp(self):
        super().setUp()
        self.grant("edit_policy_pdf", "view_policy_pdf")
        self.draft = create_draft(self.user)

    def stage_pdf(self, lines=("PIX discount 5 percent",)):
        content = text_pdf(list(lines))
        self.draft = policy_pdf.stage_policy_pdf(
            self.user,
            self.draft,
            SimpleUploadedFile("policy.pdf", content),
            expected_revision=self.draft.revision,
        )
        return content

    def valid_review(self):
        return {
            "pix_discount_percent": "5",
            "unchanged_rules_attested": "yes",
            "passage_reviews": (
                '[{"page":1,"section":"§3","topic":"payment",'
                '"audience":"public","conflict":false,"text":"PIX discount 5 percent"}]'
            ),
        }
