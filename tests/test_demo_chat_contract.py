import json
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import TransactionTestCase

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


class DemoChatCommandContractTests(TransactionTestCase):
    def setUp(self):
        call_command("load_sources", source_dir=str(DATA_DIR), verbosity=0)

    def test_demo_runs_five_scripted_source_grounded_turns_and_separates_acceptance_delivery(self):
        output = StringIO()
        call_command("demo_chat", stdout=output)
        report = json.loads(output.getvalue())
        self.assert_summary(report)
        self.assert_cases(report["interactions"])
        self.assert_source_routing(report["interactions"])
        self.assert_no_transport_identity(report)

    def assert_summary(self, report):
        self.assertEqual((report["model_mode"], report["interaction_count"]), ("scripted", 5))
        self.assertEqual((report["accepted_count"], report["delivered_count"]), (5, 5))

    def assert_cases(self, rows):
        expected = {"catalog_only", "policy_only", "catalog_and_policy", "pix_budget", "human_handoff"}
        self.assertEqual({row["case"] for row in rows}, expected)
        for row in rows:
            self.assert_row_is_bounded_and_delivered(row)

    def assert_row_is_bounded_and_delivered(self, row):
        self.assertEqual(row["reply_state"], "delivered")
        self.assertTrue(row["snapshot_version"])
        self.assertLessEqual(row["model_requests"], 4)
        self.assertLessEqual(row["tool_executions"], 4)

    def assert_source_routing(self, rows):
        expected = {
            "catalog_only": ["catalog"],
            "policy_only": ["policy"],
            "catalog_and_policy": ["catalog", "policy"],
        }
        actual = {row["case"]: row["source_types"] for row in rows if row["case"] in expected}
        self.assertEqual(actual, expected)

    def assert_no_transport_identity(self, report):
        encoded = json.dumps(report)
        for private in ("sender", "provider_id", "raw_text", "reply_body"):
            self.assertNotIn(private, encoded)
