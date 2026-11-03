from django.core.exceptions import PermissionDenied, ValidationError

from tests.test_source_bulk_fixture import SourceBulkFixture


class SourceBulkTests(SourceBulkFixture):
    def test_edit_publish_and_delete_require_independent_source_permissions(self):
        from emporio.sources.drafts import delete_record, publish_draft, stage_cell

        self.grant(self.user, "edit_products")
        with self.assertRaises(PermissionDenied):
            stage_cell(self.user, self.draft, "categories", 1, "name", "No", expected_revision=0)
        with self.assertRaises(PermissionDenied):
            delete_record(self.user, self.draft, "products", self.product_id, expected_revision=0)
        self.grant(self.user, "delete_products")
        deleted = delete_record(
            self.user, self.draft, "products", self.product_id, expected_revision=0
        )
        self.assertEqual(deleted.revision, 1)
        with self.assertRaises(PermissionDenied):
            publish_draft(self.user, self.draft, expected_revision=1)

    def test_append_skips_identical_rejects_conflict_and_keeps_existing(self):
        from emporio.sources.drafts import preview_draft, stage_upload

        before = preview_draft(self.user, self.draft)["products"]
        identical = self.upload([before[0]])
        draft = stage_upload(
            self.user, self.draft, "products", identical, mode="append", expected_revision=0
        )
        self.assertEqual(preview_draft(self.user, draft)["products"], before)
        conflicting = dict(before[0], name="different")
        with self.assertRaises(ValidationError):
            stage_upload(
                self.user,
                self.draft,
                "products",
                self.upload([conflicting]),
                mode="append",
                expected_revision=0,
            )

    def test_upsert_replaces_complete_row(self):
        draft, before, updated, after = self.upserted_products()
        self.assertEqual(len(after), len(before))
        self.assertEqual(after[0], updated)

    def test_replace_requires_delete_permission_and_publish_confirmation(self):
        draft, _, _, after = self.upserted_products()
        replacement = self.stage_replacement(draft, after)
        self.confirm_replacement(replacement, after)

    def test_upload_rejects_conflicting_duplicate_ids_and_stale_revision(self):
        from emporio.sources.drafts import preview_draft, stage_upload

        rows = preview_draft(self.user, self.draft)["products"]
        with self.assertRaises(ValidationError):
            stage_upload(
                self.user,
                self.draft,
                "products",
                self.upload([dict(rows[0]), dict(rows[0], name="Conflict")]),
                mode="upsert",
                expected_revision=0,
            )
        with self.assertRaises(ValidationError):
            stage_upload(
                self.user,
                self.draft,
                "products",
                self.upload([rows[0]]),
                mode="append",
                expected_revision=1,
            )
