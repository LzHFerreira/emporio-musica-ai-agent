from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.core.management import call_command

from emporio.catalog.models import SourceSnapshot
from tests.test_source_workflow_fixture import SourceWorkflowFixture


def _assert_staged_snapshot(test, version, base):
    from emporio.catalog.models import Category, Product, Promotion
    from emporio.orders.models import Customer, Order, OrderItem

    candidate = SourceSnapshot.objects.get(version=version)
    test.assertFalse(candidate.is_active)
    models = (Category, Product, Promotion, Customer, Order, OrderItem)
    test.assertEqual(
        [model.objects.filter(snapshot=candidate).count() for model in models],
        [model.objects.filter(snapshot=base).count() for model in models],
    )


class PublicationFailureKeepsActiveVersionAndRetryThenRepeatIsRejectedTests(SourceWorkflowFixture):
    def test_publication_failure_keeps_active_version_and_retry_then_repeat_is_rejected(self):
        from emporio.sources.drafts import create_draft, preview_draft, publish_draft, stage_cell

        self.grant("view_products", "edit_products", "publish_products")
        draft = create_draft(self.user)
        stage_cell(
            self.user,
            draft,
            "products",
            self.product.source_id,
            "name",
            "Retry publication",
            expected_revision=0,
        )
        preview_draft(self.user, draft)
        with patch("emporio.sources.draft_bundle._retain_bundle", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                publish_draft(self.user, draft, expected_revision=1)
        self.assertEqual(SourceSnapshot.objects.get(is_active=True).version, self.snapshot.version)
        draft.refresh_from_db()
        self.assertEqual(draft.status, "draft")
        published = publish_draft(self.user, draft, expected_revision=1)
        self.assertNotEqual(published.version, self.snapshot.version)
        with self.assertRaises(PermissionDenied):
            publish_draft(self.user, draft, expected_revision=1)

    def test_snapshot_rows_are_staged_before_activation_and_failure_keeps_pointer(self):
        from emporio.sources import draft_publication
        from emporio.sources.drafts import create_draft, preview_draft, publish_draft, stage_cell

        self.grant("view_products", "edit_products", "publish_products")
        draft = create_draft(self.user)
        stage_cell(
            self.user,
            draft,
            "products",
            self.product.source_id,
            "name",
            "Staged",
            expected_revision=0,
        )
        preview_draft(self.user, draft)
        old_version = self.snapshot.version
        candidate_version = []

        def fail_activation(version, *args):
            candidate_version.append(version)
            _assert_staged_snapshot(self, version, self.snapshot)
            raise OSError("activation unavailable")

        with patch.object(draft_publication, "_activate", side_effect=fail_activation):
            with self.assertRaises(OSError):
                publish_draft(self.user, draft, expected_revision=1)
        staged = SourceSnapshot.objects.get(version=candidate_version[0])
        self.assertFalse(staged.is_active)
        self.assertEqual(SourceSnapshot.objects.get(is_active=True).version, old_version)


class NoopPublicationAndLegacyImportBlockAfterManagedPublicationTests(SourceWorkflowFixture):
    def test_noop_publication_and_legacy_import_block_after_managed_publication(self):
        from django.core.management.base import CommandError

        from emporio.sources.drafts import create_draft, preview_draft, publish_draft, stage_cell

        self.grant("publish_sources", "view_products", "edit_products", "publish_products")
        noop = create_draft(self.user)
        preview_draft(self.user, noop)
        original = publish_draft(self.user, noop, expected_revision=0)
        self.assertEqual(original.version, self.snapshot.version)
        draft = create_draft(self.user)
        stage_cell(
            self.user,
            draft,
            "products",
            self.product.source_id,
            "name",
            "Managed",
            expected_revision=0,
        )
        preview_draft(self.user, draft)
        publish_draft(self.user, draft, expected_revision=1)
        with self.assertRaises(CommandError):
            call_command("load_sources", source_dir=str(self.sources), verbosity=0)


class PublishRequestDeletionConfirmationTest(SourceWorkflowFixture):
    def test_publish_requests_require_preview_and_deletion_confirmation(self):
        from django.test import RequestFactory

        from emporio.sources import source_publish_views

        draft = self.staged_removal_draft()
        factory = RequestFactory()
        preview = factory.get("/preview/")
        preview.user = self.user
        self.assertEqual(source_publish_views.source_preview(preview, draft.pk).status_code, 200)
        post = factory.post("/publish/", {"revision": str(draft.revision)})
        post.user = self.user
        self.assertEqual(source_publish_views.source_publish(post, draft.pk).status_code, 400)
        post = factory.post(
            "/publish/", {"revision": str(draft.revision), "confirm_deletions": "yes"}
        )
        post.user = self.user
        self.assertEqual(source_publish_views.source_publish(post, draft.pk).status_code, 302)
        self.assertEqual(source_publish_views.source_preview(preview, draft.pk).status_code, 200)


class RollbackRequestReasonAndAuthenticationTest(SourceWorkflowFixture):
    def test_rollback_request_requires_reason_and_authenticated_user(self):
        from django.test import RequestFactory

        from emporio.sources import source_publish_views

        draft = self.staged_removal_draft()
        factory = RequestFactory()
        post = factory.post("/rollback/", {"reason": ""})
        post.user = self.user
        self.assertEqual(
            source_publish_views.source_rollback(post, draft.base_version).status_code, 400
        )
        anonymous = factory.get("/preview/")
        anonymous.user = SimpleNamespace(is_authenticated=False)
        self.assertEqual(source_publish_views.source_preview(anonymous, draft.pk).status_code, 302)


class PublishRequestAuthErrorsAndInvalidRevisionAreBoundedTests(SourceWorkflowFixture):
    def test_publish_request_auth_errors_and_invalid_revision_are_bounded(self):
        from django.test import RequestFactory

        from emporio.sources import source_publish_views
        from emporio.sources.drafts import create_draft

        factory = RequestFactory()
        draft = create_draft(self.user)
        anonymous = factory.post("/publish/")
        anonymous.user = SimpleNamespace(is_authenticated=False)
        self.assertEqual(source_publish_views.source_publish(anonymous, draft.pk).status_code, 302)
        post = factory.post("/publish/")
        post.user = self.user
        self.assertEqual(source_publish_views.source_publish(post, draft.pk).status_code, 403)
        self.grant("view_products", "edit_products", "publish_products")
        post = factory.post("/publish/", {"revision": "bad"})
        post.user = self.user
        self.assertEqual(source_publish_views.source_publish(post, draft.pk).status_code, 400)
        get = factory.get("/preview/")
        get.user = self.user
        from django.http import Http404

        with self.assertRaises(Http404):
            source_publish_views.source_preview(get, 999999)
