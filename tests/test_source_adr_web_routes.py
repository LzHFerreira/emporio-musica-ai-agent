from emporio.sources.read import CSV_HEADERS
from tests.test_source_workflow_fixture import SourceWorkflowFixture


class DraftDataIdentityEditAndDeletionValidationEdgesTests(SourceWorkflowFixture):
    def test_draft_data_identity_edit_and_deletion_validation_edges(self):
        from emporio.sources.draft_data import (
            _apply_identity_edits,
            _complete_row,
            _matching_rows,
            _valid_delete,
        )
        from emporio.sources.read import SourceImportError

        row = {"product_id": "1", "name": "A"}
        self.assertEqual(_matching_rows([row], {"product_id": "1"}), [row])
        with self.assertRaises(SourceImportError):
            _matching_rows([row, dict(row)], {"product_id": "1"})
        deletion = {"field": "__deleted__", "value": "true"}
        self.assertTrue(_valid_delete([deletion], [deletion], [row]))
        self.assertFalse(_valid_delete([deletion], [deletion], []))
        with self.assertRaises(SourceImportError):
            _apply_identity_edits([row], "products", ["1"], [deletion, deletion])
        with self.assertRaises(SourceImportError):
            _apply_identity_edits([row], "products", ["1"], [{"field": "bad", "value": "x"}])
        self.assertTrue(
            _complete_row(
                "products",
                {"product_id": "1"},
                {field: "" for field in CSV_HEADERS["products"]} | {"product_id": "1"},
            )
        )
        self.assertFalse(_complete_row("products", {"product_id": "1"}, {"product_id": "2"}))
