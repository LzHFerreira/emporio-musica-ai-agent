"""Contract tests for the full store manual model tool."""

from emporio import policy
from emporio.agent import _handlers
from emporio.catalog.models import SourceSnapshot
from tests.test_source_workflow_fixture import SourceWorkflowFixture


class ReadStoreManualContractTests(SourceWorkflowFixture):
    def test_active_manual_returns_every_page_with_text(self):
        result = policy.read_store_manual()
        self.assertEqual(result["outcome"], "found")
        self.assertEqual(set(result), {"outcome", "data", "sources", "page", "pagination_restarted", "has_more", "error_category"})
        self.assertEqual([item["page"] for item in result["data"]], list(range(1, 9)))
        self.assertIn("PIX", "".join(item["text"] for item in result["data"]))

    def test_missing_active_snapshot_is_source_unavailable(self):
        SourceSnapshot.objects.update(is_active=False)
        result = policy.read_store_manual()
        self.assertEqual((result["outcome"], result["error_category"]), ("error", "source_unavailable"))

    def test_handler_is_registered_for_the_agent(self):
        self.assertIn("read_store_manual", _handlers())
