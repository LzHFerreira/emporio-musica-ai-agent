from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.db import DatabaseError
from django.test import TestCase

from emporio.catalog.models import SourceSnapshot
from emporio.policy import lookup_public_policy
from emporio.sources.read import SourceImportError
DATA_DIR = Path(__file__).resolve().parents[1] / "data"


class PolicyRetrievalTests(TestCase):
    def setUp(self):
        call_command("load_sources", source_dir=str(DATA_DIR), verbosity=0)

    def save_passages(self, snapshot, passages):
        snapshot.manifest["policy"]["passages"] = passages
        snapshot.save(update_fields=["manifest"])

    def test_public_hours_have_provenance_and_internal_policy_is_never_returned(self):
        result = lookup_public_policy(query="horário", topic="hours")
        passage = result["data"][0]
        self.assertEqual((passage["page"], passage["section"]), (2, "§2"))
        self.assertRegex(passage["text"], r"09:00.*18:00")
        active = SourceSnapshot.objects.get(is_active=True)
        self.assertTrue(
            any(
                source["bundle_version"] == active.version
                and (source["page"], source["section"]) == (2, "§2")
                for source in result["sources"]
            )
        )
        internal = lookup_public_policy(query="consultar gerência em caso de dúvidas")
        self.assertEqual(internal["data"], [])

    def test_policy_lookup_rejects_bad_arguments_and_distinguishes_no_match(self):
        for query, topic in ((None, None), ("x" * 501, None), ("hours", 1)):
            result = lookup_public_policy(query=query, topic=topic)
            self.assertEqual((result["outcome"], result["error_category"]), ("error", "invalid_arguments"))
        missing = lookup_public_policy(query="unmatched invented vocabulary")
        self.assertEqual(missing["outcome"], "not_found")
        self.assertIsNone(missing["error_category"])

    def test_policy_lookup_handles_missing_active_snapshot_and_storage_errors(self):
        SourceSnapshot.objects.update(is_active=False)
        unavailable = lookup_public_policy(query="hours")
        self.assertEqual((unavailable["outcome"], unavailable["error_category"]), ("error", "source_unavailable"))
        with patch.object(SourceSnapshot.objects, "filter", side_effect=DatabaseError("locked")):
            unavailable = lookup_public_policy(query="hours")
        self.assertEqual((unavailable["outcome"], unavailable["error_category"]), ("error", "source_unavailable"))

    def test_policy_lookup_filters_malformed_internal_and_unbounded_passages(self):
        snapshot = SourceSnapshot.objects.get(is_active=True)
        self.save_passages(snapshot, [
            None,
            {"audience": "internal", "text": "hours secret"},
            {"audience": "public", "text": None},
            {"audience": "public", "text": "  "},
            {"audience": "public", "text": "x" * 401},
        ])
        result = lookup_public_policy(query="hours", topic="hours")
        self.assertEqual(result["outcome"], "not_found")

        self.save_passages(snapshot, [
            {
                "audience": "public",
                "topic": "hours",
                "text": "hours open",
                "page": 2,
                "section": "§2",
                "conflict": False,
            }
        ])
        with patch("emporio.policy.verify_snapshot_pdf", side_effect=SourceImportError("hash mismatch")):
            malformed = lookup_public_policy(query="hours", topic="hours")
        self.assertEqual((malformed["outcome"], malformed["error_category"]), ("error", "source_unavailable"))
