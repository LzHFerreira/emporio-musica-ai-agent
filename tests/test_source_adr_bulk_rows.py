import csv
import io
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.urls import reverse

from emporio.sources.read import CSV_FILES, CSV_HEADERS
from tests.test_source_workflow_fixture import SourceWorkflowFixture


class PreviewOwnerAndPublishReviewGateRejectUnreviewedOrUnauthorizedRequestsTests(
    SourceWorkflowFixture
):
    def test_preview_owner_and_publish_review_gate_reject_unreviewed_or_unauthorized_requests(self):
        from emporio.sources.drafts import create_draft, stage_cell

        self.grant("view_products", "edit_products", "publish_products")
        self.login()
        draft = create_draft(self.user)
        stage_cell(
            self.user,
            draft,
            "products",
            self.product.source_id,
            "name",
            "Novo",
            expected_revision=0,
        )
        other = get_user_model().objects.create_user("other", password="secret", is_staff=True)
        self.login(other)
        self.assertEqual(
            self.client.get(reverse("staff-source-preview", args=[draft.pk])).status_code, 403
        )
        self.client.logout()
        self.login()
        publish = reverse("staff-source-publish", args=[draft.pk])
        self.client.get(reverse("staff-source-detail", args=["products"]))
        self.assertEqual(self.post_csrf(publish, {"revision": "1"}).status_code, 400)
        self.assertEqual(
            self.client.get(reverse("staff-source-preview", args=[draft.pk])).status_code, 200
        )
        self.assertEqual(self.post_csrf(publish, {"revision": "0"}).status_code, 400)
        self.assertEqual(self.post_csrf(publish, {"revision": "1"}).status_code, 302)


class WebFormsCoverUnauthenticatedMissingIdentityAndDateValidationTests(SourceWorkflowFixture):
    def test_web_forms_cover_unauthenticated_missing_identity_and_date_validation(self):

        edit_url = reverse("staff-source-edit", args=["products", self.product.source_id])
        self.assertEqual(self.client.get(edit_url).status_code, 302)
        self.login()
        upload_url = reverse("staff-source-upload", args=["products"])
        self.assertEqual(self.client.get(upload_url).status_code, 403)
        self.grant("view_products", "edit_products", "view_orders", "edit_orders")
        self.assertEqual(
            self.client.get(reverse("staff-source-edit", args=["products", "1|2"])).status_code, 400
        )
        self.assertEqual(
            self.client.get(reverse("staff-source-edit", args=["products", "999999"])).status_code,
            400,
        )
        order = next(
            csv.DictReader((self.sources / CSV_FILES["orders"]).open(encoding="utf-8-sig"))
        )
        order_edit = reverse("staff-source-edit", args=["orders", order["order_id"]])
        self.client.get(order_edit)
        bad = self.post_csrf(order_edit, {"field": "order_date", "value": "bad-date"})
        self.assertEqual(bad.status_code, 400)
        good = self.post_csrf(order_edit, {"field": "order_date", "value": "2025-10-20"})
        self.assertEqual(good.status_code, 302)


class BulkParsesAllSixSourcesTest(SourceWorkflowFixture):
    def test_bulk_upload_parses_each_canonical_source(self):
        from emporio.sources.drafts import create_draft, stage_upload

        self.grant(*[f"edit_{name}" for name in CSV_HEADERS])
        draft = create_draft(self.user)
        for source, filename in CSV_FILES.items():
            content = (self.sources / filename).read_bytes()
            updated = stage_upload(
                self.user, draft, source, io.BytesIO(content), mode="append", expected_revision=0
            )
            self.assertEqual(updated.revision, 0)


class BulkUploadRejectsBadInputsTest(SourceWorkflowFixture):
    def test_bulk_upload_rejects_invalid_mode_size_and_io(self):
        from django.core.exceptions import ValidationError

        from emporio.sources.bulk_csv import MAX_UPLOAD_BYTES
        from emporio.sources.drafts import create_draft, stage_upload

        self.grant("edit_products")
        draft = create_draft(self.user)
        cases = (
            (io.BytesIO(b""), "invalid"),
            (io.BytesIO(b"x" * (MAX_UPLOAD_BYTES + 1)), "append"),
            (SimpleNamespace(read=lambda _: (_ for _ in ()).throw(OSError())), "append"),
        )
        for stream, mode in cases:
            with self.assertRaises(ValidationError):
                stage_upload(self.user, draft, "products", stream, mode=mode, expected_revision=0)


TYPED_FIELDS = (
    ("products", "product_id", "1"),
    ("orders", "order_id", "1"),
    ("customers", "customer_id", "1"),
    ("products", "quantity", "1"),
    ("products", "stock_quantity", "0"),
    ("products", "price_brl", "1.00"),
    ("orders", "total_brl", "1.00"),
    ("promotions", "discount_percent", "5"),
    ("promotions", "is_active", "true"),
    ("products", "specs", "{}"),
    ("products", "created_at", "2025-01-01"),
    ("orders", "order_date", "1/2/2025"),
    ("products", "name", "A"),
    ("products", "description", " optional "),
)


class BulkCsvTypedFieldsTest(SourceWorkflowFixture):
    def test_csv_parser_converts_all_supported_typed_fields(self):
        from emporio.sources.bulk_csv import field_value

        for source, field, value in TYPED_FIELDS:
            self.assertIsNotNone(field_value(source, field, value))

    def test_csv_parser_handles_optional_dates_and_invalid_columns(self):
        from django.core.exceptions import ValidationError

        from emporio.sources.bulk_csv import field_value, read_upload

        self.assertIsNone(field_value("orders", "estimated_delivery", ""))
        self.assertEqual(
            field_value("orders", "estimated_delivery", "1/5/2025"),
            field_value("orders", "order_date", "1/5/2025"),
        )
        with self.assertRaises(ValidationError):
            read_upload(io.StringIO("wrong\n1\n"), "products")


class BulkDuplicateMergeTest(SourceWorkflowFixture):
    def test_duplicate_merge_skips_identicals_and_rejects_conflicts(self):
        from django.core.exceptions import ValidationError

        from emporio.sources.bulk_merge import merge_rows

        row = next(
            csv.DictReader((self.sources / CSV_FILES["customers"]).open(encoding="utf-8-sig"))
        )
        self.assertEqual(len(merge_rows("customers", [row], [row, dict(row)], "append")), 1)
        with self.assertRaises(ValidationError):
            merge_rows("customers", [row], [row, dict(row, name="Other")], "upsert")
