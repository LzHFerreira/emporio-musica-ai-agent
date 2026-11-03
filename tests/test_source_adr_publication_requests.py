import csv
import io

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied

from emporio.catalog.models import Product, SourceAuditEvent
from emporio.sources.read import CSV_FILES, CSV_HEADERS
from tests.test_source_workflow_fixture import SourceWorkflowFixture


class SafeProductDeletionRoundtripTests(SourceWorkflowFixture):
    def test_deleting_product_with_no_order_or_promotion_reference(self):
        from emporio.sources.drafts import create_draft, delete_record, preview_draft

        self.grant("view_products", "edit_products", "delete_products")
        draft = create_draft(self.user)
        safe = self.safe_product(preview_draft(self.user, draft)["products"])
        deleted = delete_record(
            self.user, draft, "products", safe["product_id"], expected_revision=0
        )
        self.assertEqual(
            len(preview_draft(self.user, deleted)["products"]),
            Product.objects.filter(snapshot=self.snapshot).count() - 1,
        )


class CustomerAppendRoundtripTests(SourceWorkflowFixture):
    def test_appending_customer_is_visible_in_preview(self):
        from emporio.sources.drafts import create_draft, preview_draft, stage_upload

        self.grant("view_customers", "edit_customers")
        draft = create_draft(self.user)
        customers = list(
            csv.DictReader((self.sources / CSV_FILES["customers"]).open(encoding="utf-8-sig"))
        )
        new_customer = dict(
            customers[-1],
            customer_id=str(max(int(row["customer_id"]) for row in customers) + 100),
            name="Cliente novo",
        )
        stream = io.StringIO()
        writer = csv.DictWriter(stream, fieldnames=CSV_HEADERS["customers"])
        writer.writeheader()
        writer.writerow(new_customer)
        stream.seek(0)
        inserted = stage_upload(
            self.user, draft, "customers", stream, mode="append", expected_revision=0
        )
        self.assertIn(new_customer, preview_draft(self.user, inserted)["customers"])


class ServiceRejectsUnknownSourcesModesRowsRevisionsAndInvalidDraftsTests(SourceWorkflowFixture):
    def test_service_rejects_unknown_source_mode_and_stale_revision(self):
        from django.core.exceptions import ValidationError

        from emporio.sources.drafts import create_draft, stage_upload

        self.grant("edit_products")
        draft = create_draft(self.user)
        content = (self.sources / CSV_FILES["products"]).read_bytes()
        for source, mode, revision in (
            ("unknown", "append", 0),
            ("products", "bad", 0),
            ("products", "append", 2),
        ):
            with self.assertRaises(ValidationError):
                stage_upload(
                    self.user,
                    draft,
                    source,
                    io.BytesIO(content),
                    mode=mode,
                    expected_revision=revision,
                )

    def test_service_rejects_invalid_identity_delete_and_draft_rows(self):
        from django.core.exceptions import ValidationError

        from emporio.sources.drafts import create_draft, delete_record, stage_cell

        self.grant("edit_products", "delete_products")
        draft = create_draft(self.user)
        with self.assertRaises(ValidationError):
            stage_cell(
                self.user,
                draft,
                "products",
                self.product.source_id,
                "product_id",
                "9",
                expected_revision=0,
            )
        with self.assertRaises(ValidationError):
            stage_cell(self.user, draft, "products", 999999, "name", "missing", expected_revision=0)
        with self.assertRaises(ValidationError):
            delete_record(self.user, draft, "unknown", 1, expected_revision=0)
        with self.assertRaises(ValidationError):
            delete_record(self.user, draft, "products", "not-a-number", expected_revision=0)

    def test_service_rejects_malformed_draft_and_records_audit(self):
        from emporio.sources.drafts import create_draft, preview_draft
        from emporio.sources.read import SourceImportError

        self.grant("view_products", "edit_products")
        draft = create_draft(self.user)
        draft.sources = [
            {
                "source": "products",
                "identity": [str(self.product.source_id)],
                "field": "bogus",
                "value": "x",
            }
        ]
        draft.save(update_fields=["sources"])
        with self.assertRaises(SourceImportError):
            preview_draft(self.user, draft)
        self.assertTrue(
            SourceAuditEvent.objects.filter(draft=draft, event="mutation_rejected").exists()
        )


class BundleVerificationAndStaffStateAreEnforcedTests(SourceWorkflowFixture):
    def test_bundle_verification_and_staff_state_are_enforced(self):
        from emporio.sources.drafts import create_draft, preview_draft
        from emporio.sources.read import SourceImportError

        draft = create_draft(self.user)
        self.grant("view_products")
        bundle = self.bundle_root / draft.base_version
        csv_path = bundle / CSV_FILES["products"]
        original = csv_path.read_bytes()
        csv_path.write_bytes(original + b" tamper")
        with self.assertRaises(SourceImportError):
            preview_draft(self.user, draft)
        csv_path.write_bytes(original)
        inactive = get_user_model().objects.create_user("inactive", is_staff=True, is_active=False)
        with self.assertRaises(PermissionDenied):
            preview_draft(inactive, draft)
        self.assertTrue(
            SourceAuditEvent.objects.filter(draft=draft, outcome="validation_rejected").exists()
        )


class BundleSchemaMismatchAndValidationRejectionsAreAuditedTests(SourceWorkflowFixture):
    def test_bundle_schema_mismatch_and_validation_rejections_are_audited(self):
        from django.core.exceptions import ValidationError

        from emporio.sources.drafts import create_draft, preview_draft, stage_upload
        from emporio.sources.read import SourceImportError

        self.grant("view_products", "edit_products")
        draft = create_draft(self.user)
        bundle = self.bundle_root / draft.base_version
        extra = bundle / "unexpected"
        extra.write_text("x")
        with self.assertRaises(SourceImportError):
            preview_draft(self.user, draft)
        extra.unlink()
        product = dict(
            next(csv.DictReader((self.sources / CSV_FILES["products"]).open(encoding="utf-8-sig"))),
            category_id="999999",
        )
        stream = io.StringIO()
        writer = csv.DictWriter(stream, fieldnames=CSV_HEADERS["products"])
        writer.writeheader()
        writer.writerow(product)
        stream.seek(0)
        with self.assertRaises(ValidationError):
            stage_upload(self.user, draft, "products", stream, mode="upsert", expected_revision=0)
        self.assertTrue(
            SourceAuditEvent.objects.filter(draft=draft, event="mutation_rejected").exists()
        )
