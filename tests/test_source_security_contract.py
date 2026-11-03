"""Source manifest and active-pointer integrity contracts."""

from emporio.policy import lookup_public_policy
from tests.test_source_workflow_fixture import SourceWorkflowFixture


class SourceSecurityContractTests(SourceWorkflowFixture):
    def test_policy_passages_require_positive_page_and_nonempty_section(self):
        snapshot = self.snapshot
        snapshot.manifest["policy"]["passages"] = [
            {"audience": "public", "topic": "hours", "text": "hours store open",
             "page": 0, "section": "§2", "conflict": False},
            {"audience": "public", "topic": "hours", "text": "hours store open",
             "page": 999, "section": " ", "conflict": False},
        ]
        snapshot.save(update_fields=["manifest"])
        result = lookup_public_policy(query="hours store open", topic="hours")
        self.assertEqual(result["outcome"], "not_found")

    def test_equal_rank_policy_ties_use_stable_page_and_section_order(self):
        snapshot = self.snapshot
        snapshot.manifest["policy"]["passages"] = [
            {"audience": "public", "topic": "hours", "text": "hours store opens",
             "page": 4, "section": "§4", "conflict": False},
            {"audience": "public", "topic": "hours", "text": "hours store opens",
             "page": 2, "section": "§2", "conflict": False},
        ]
        snapshot.save(update_fields=["manifest"])
        result = lookup_public_policy(query="hours store opens", topic="hours")
        self.assertEqual([(p["page"], p["section"]) for p in result["data"]], [(2, "§2"), (4, "§4")])
