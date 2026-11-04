"""Contract tests for the full store manual model tool."""

from emporio import policy
from emporio.agent import _handlers
from emporio.catalog.models import SourceSnapshot
from tests.test_source_workflow_fixture import SourceWorkflowFixture


class ReadStoreManualContractTests(SourceWorkflowFixture):
    def test_active_manual_returns_only_public_reviewed_passages(self):
        result = policy.read_store_manual()
        self.assertEqual(result["outcome"], "found")
        self.assertEqual(set(result), {"outcome", "data", "sources", "page", "pagination_restarted", "has_more", "error_category"})
        passages = self.snapshot.manifest["policy"]["passages"]
        joined = " ".join(item["text"] for item in result["data"])
        for passage in passages:
            if passage["audience"] != "public":
                self.assertNotIn(passage["text"], joined)
        public = {(p["page"], p["text"]) for p in passages if p["audience"] == "public"}
        self.assertTrue(result["data"])
        for item in result["data"]:
            self.assertIn((item["page"], item["text"]), public)
        self.assertIn("PIX", joined)

    def test_active_manual_sources_are_policy_records(self):
        result = policy.read_store_manual()
        self.assertTrue(result["sources"])
        self.assertTrue(all(source["type"] == "policy" for source in result["sources"]))

    def test_missing_active_snapshot_is_source_unavailable(self):
        SourceSnapshot.objects.update(is_active=False)
        result = policy.read_store_manual()
        self.assertEqual((result["outcome"], result["error_category"]), ("error", "source_unavailable"))

    def test_handler_is_registered_for_the_agent(self):
        self.assertIn("read_store_manual", _handlers())
