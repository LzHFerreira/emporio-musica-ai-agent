from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory
from django.urls import reverse

from emporio.catalog.models import SourceDraft
from emporio.sources import source_edit_views
from emporio.sources.read import CSV_FILES
from tests.test_source_workflow_fixture import SourceWorkflowFixture, workflow_request


class RollbackRequiresPermissionReasonAndActiveVersionTests(SourceWorkflowFixture):
    def test_rollback_requires_permission_reason_and_active_version(self):
        from emporio.sources.drafts import rollback_sources

        with self.assertRaises(PermissionDenied):
            rollback_sources(
                self.user,
                self.snapshot.version,
                expected_version=self.snapshot.version,
                reason="valid",
            )
        self.grant("rollback_sources", "view_products")
        self.login()
        rollback = reverse("staff-source-rollback", args=[self.snapshot.version])
        self.client.get(reverse("staff-source-detail", args=["products"]))
        self.assertEqual(
            self.post_csrf(
                rollback, {"expected_version": self.snapshot.version, "reason": ""}
            ).status_code,
            400,
        )
        self.assertEqual(
            self.post_csrf(rollback, {"expected_version": "stale", "reason": "reason"}).status_code,
            400,
        )


class RemainingPermissionBundleAndRollbackRejectionBoundariesTests(SourceWorkflowFixture):
    def test_remaining_permission_bundle_and_rollback_rejection_boundaries(self):
        from django.core.exceptions import PermissionDenied

        from emporio.sources.draft_data import bundle, staff_user
        from emporio.sources.read import SourceImportError

        with self.assertRaises(PermissionDenied):
            staff_user(SimpleNamespace(is_authenticated=False))
        with self.assertRaises(PermissionDenied):
            staff_user(SimpleNamespace(is_authenticated=True, pk=999999))
        inactive = get_user_model().objects.create_user("disabled", is_staff=True, is_active=False)
        with self.assertRaises(PermissionDenied):
            staff_user(inactive)
        with self.assertRaises(SourceImportError):
            bundle(SimpleNamespace(version="../escape", manifest={}))
        with self.assertRaises(SourceImportError):
            bundle(SimpleNamespace(version="missing", manifest={}))


class InvalidDraftRowsAndRollbackBoundariesAreRejectedTests(SourceWorkflowFixture):
    def test_invalid_draft_rows_and_rollback_boundaries_are_rejected(self):
        from django.core.exceptions import ValidationError

        from emporio.sources import rollback
        from emporio.sources.draft_data import _new_row
        from emporio.sources.read import SourceImportError

        with self.assertRaises(SourceImportError):
            _new_row("products", {"product_id": "1"}, [])
        with self.assertRaises(SourceImportError):
            _new_row("products", {"product_id": "1"}, [{"field": "name", "value": "x"}])
        with self.assertRaises(ValidationError):
            rollback._validate_rollback_rows({"products": []})
        with self.assertRaises(ValidationError):
            rollback._verify_file(self.bundle_root, "missing.csv", "expected")
        target = SimpleNamespace(
            manifest={"changed": True}, pricing_rule_version="r1", pix_basis_points=5
        )
        inspected = SimpleNamespace(manifest={}, pricing_rule_version="r1", pix_basis_points=5)
        with self.assertRaises(ValidationError):
            rollback._check_target_unchanged(target, inspected)
        rollback._check_target_unchanged(inspected, inspected)
        self.assertEqual(rollback._reason("  reviewed   rollback  "), "reviewed rollback")


class EditHandlerDirectRequestsTest(SourceWorkflowFixture):
    def test_edit_handler_validates_and_stages_session_requests(self):
        self.grant("view_products", "edit_products")
        factory = RequestFactory()
        path = f"/equipe/fontes/products/{self.product.source_id}/editar/"
        get = workflow_request(factory, self.user, "get", path)
        self.assertEqual(
            source_edit_views.source_edit(get, "products", str(self.product.source_id)).status_code,
            200,
        )
        bad = workflow_request(factory, self.user, "get", path)
        self.assertEqual(
            source_edit_views.source_edit(bad, "products", "bad|identity").status_code, 400
        )
        post = workflow_request(
            factory, self.user, "post", path, {"field": "name", "value": "Direct edit"}
        )
        self.assertEqual(
            source_edit_views.source_edit(
                post, "products", str(self.product.source_id)
            ).status_code,
            302,
        )
        self.assertEqual(source_edit_views._form_value("order_date", "2025-10-20"), "10/20/2025")
        self.assertEqual(source_edit_views._form_value("order_date", "2025-01-02"), "01/02/2025")
        with self.assertRaises(ValueError):
            source_edit_views._form_value("order_date", "bad")
        with self.assertRaises(Exception):
            source_edit_views._revision(
                SimpleNamespace(POST={"revision": "bad"}), SimpleNamespace(revision=0)
            )


class UploadHandlerDirectRequestsTest(SourceWorkflowFixture):
    def test_upload_handler_validates_and_stages_session_requests(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import RequestFactory

        from emporio.sources import source_upload_views
        from tests.test_source_workflow_fixture import workflow_request

        self.grant("view_products", "edit_products")
        factory = RequestFactory()
        path = "/equipe/fontes/products/enviar/"
        get = workflow_request(factory, self.user, "get", path)
        self.assertEqual(source_upload_views.source_upload(get, "products").status_code, 200)
        post = workflow_request(factory, self.user, "post", path)
        self.assertEqual(source_upload_views.source_upload(post, "products").status_code, 400)
        upload = SimpleUploadedFile(
            CSV_FILES["products"],
            (self.sources / CSV_FILES["products"]).read_bytes(),
            content_type="text/csv",
        )
        post = workflow_request(
            factory, self.user, "post", path, {"file": upload, "mode": "append"}
        )
        self.assertEqual(source_upload_views.source_upload(post, "products").status_code, 200)
        self.assertEqual(
            source_upload_views._revision(SimpleNamespace(POST={}), SimpleNamespace(revision=3)), 3
        )
        context = source_upload_views.preview_context(
            self.user, SourceDraft.objects.filter(author=self.user).last(), {"products": []}
        )
        self.assertIn("counts", context)


class AuditIgnoresUnknownActorAndPublishViewFormatsFailureResponsesTests(SourceWorkflowFixture):
    def test_error_helpers_escape_injected_markup(self):
        from emporio.sources.source_publish_views import _error_response

        payload = "<script>alert(1)</script>"
        reflected = _error_response(ValueError(f"invalid columns: {payload}"))
        self.assertIn(b"&lt;script&gt;", reflected.content)
        self.assertNotIn(b"<script>", reflected.content)
        from django.test import RequestFactory

        request = workflow_request(RequestFactory(), self.user, "post", "/edit/")
        response = source_edit_views._bad_edit_request(request, "products", payload, payload)
        self.assertIn(b"&lt;script&gt;", response.content)
        self.assertNotIn(b"<script>", response.content)

    def test_audit_ignores_unknown_actor_and_publish_view_formats_failure_responses(self):
        from django.core.exceptions import PermissionDenied, ValidationError
        from django.test import RequestFactory

        from emporio.sources import source_publish_views
        from emporio.sources.draft_audit import record_rejected
        from emporio.sources.drafts import create_draft

        record_rejected(SimpleNamespace(pk=999999), None, "unknown", ValueError("hidden"))
        self.grant("view_products")
        draft = create_draft(self.user)
        factory = RequestFactory()
        get = factory.get("/preview/")
        get.user = self.user
        with patch(
            "emporio.sources.source_publish_views.draft_services.preview_draft",
            side_effect=PermissionDenied("denied"),
        ):
            self.assertEqual(source_publish_views.source_preview(get, draft.pk).status_code, 403)
        with patch(
            "emporio.sources.source_publish_views.draft_services.preview_draft",
            side_effect=ValidationError("invalid"),
        ):
            self.assertEqual(source_publish_views.source_preview(get, draft.pk).status_code, 400)
        self.assertEqual(source_publish_views._error_response(PermissionDenied()).status_code, 403)
        self.assertEqual(
            source_publish_views._error_response(ValidationError("invalid")).status_code, 400
        )
