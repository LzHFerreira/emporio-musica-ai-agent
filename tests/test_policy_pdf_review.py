from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError

from emporio.sources import policy_pdf, policy_pdf_review
from tests.policy_pdf_test_support import PolicyPdfTestSupport


class PolicyPdfReviewTests(PolicyPdfTestSupport):
    def test_review_requires_staging_and_unchanged_rule_attestation(self):
        with self.assertRaises(ValidationError):
            policy_pdf.review_policy_pdf(self.user, self.draft, self.valid_review(), expected_revision=0)
        self.stage_pdf()
        values = {**self.valid_review(), "unchanged_rules_attested": "no"}
        with self.assertRaises(ValidationError):
            policy_pdf.review_policy_pdf(self.user, self.draft, values, expected_revision=1)

    def test_review_rejects_malformed_oversized_and_stale_values(self):
        self.stage_pdf()
        invalid = ("{", None, "x" * (128 * 1024 + 1))
        for passage_reviews in invalid:
            values = {**self.valid_review(), "passage_reviews": passage_reviews}
            with self.subTest(passage_reviews=type(passage_reviews)), self.assertRaises(ValidationError):
                policy_pdf.review_policy_pdf(self.user, self.draft, values, expected_revision=1)
        values = {**self.valid_review(), "pix_discount_percent": "3"}
        with self.assertRaises(ValidationError):
            policy_pdf.review_policy_pdf(self.user, self.draft, values, expected_revision=1)
        with self.assertRaises(ValidationError):
            policy_pdf.review_policy_pdf(self.user, self.draft, self.valid_review(), expected_revision=2)

    def test_review_rejects_missing_or_invalid_pix_evidence(self):
        for pages in (["No payment details"], ["PIX discount 100 percent"]):
            with self.subTest(pages=pages), self.assertRaises(ValidationError):
                policy_pdf_review._check_pix_evidence(pages, 500)
        self.assertIsNone(policy_pdf_review._check_pix_evidence(["PIX 3 percent", "PIX 5 percent"], 500))

    def invalid_passages(self):
        valid = {"page": 1, "section": "§3", "topic": "payment", "audience": "public", "conflict": False, "text": "PIX discount 5 percent"}
        changes = (
            {"unexpected": True},
            {**valid, "page": True},
            {**valid, "page": 2},
            {**valid, "section": ""},
            {**valid, "section": None},
            {**valid, "topic": "unknown"},
            {**valid, "topic": None},
            {**valid, "audience": "bad"},
            {**valid, "audience": None},
            {**valid, "conflict": 0},
            {**valid, "text": "not present"},
            {**valid, "text": ""},
            {**valid, "text": "X" * 401},
        )
        return valid, changes

    def assert_invalid_passages(self, values):
        for item in values:
            with self.subTest(item=item), self.assertRaises(ValidationError):
                policy_pdf_review._validate_passages([item], ["PIX discount 5 percent"])

    def test_review_validates_passage_fields_and_text_spans(self):
        _, invalid = self.invalid_passages()
        self.assert_invalid_passages(invalid)

    def test_review_requires_passages_for_every_page_and_limits_count(self):
        valid, _ = self.invalid_passages()
        for passages, pages in (([], ["PIX discount 5 percent"]), ([valid], ["PIX discount 5 percent", "other"]), ([{}] * 201, ["PIX discount 5 percent"])):
            with self.subTest(count=len(passages), pages=len(pages)), self.assertRaises(ValidationError):
                policy_pdf_review._validate_passages(passages, pages)

    def test_review_requires_edit_permission_and_rechecks_candidate_hash(self):
        self.stage_pdf()
        stranger = type("User", (), {"is_authenticated": True, "pk": -1})()
        with self.assertRaises(PermissionDenied):
            policy_pdf.review_policy_pdf(stranger, self.draft, self.valid_review(), expected_revision=1)
        locked = self.draft.__class__.objects.get(pk=self.draft.pk)
        locked.policy["candidate_sha256"] = "changed"
        with patch.object(self.draft.__class__.objects, "select_for_update") as select:
            select.return_value.get.return_value = locked
            with self.assertRaises(ValidationError):
                policy_pdf.review_policy_pdf(self.user, self.draft, self.valid_review(), expected_revision=1)
