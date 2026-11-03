"""Validate public catalog and policy service errors and provenance bounds."""

from unittest.mock import patch

from django.db import DatabaseError

from emporio.catalog import search_catalog
from emporio.catalog.models import SourceSnapshot
from emporio.policy import lookup_public_policy
from emporio.sources.read import SourceImportError
from tests.test_source_workflow_fixture import SourceWorkflowFixture


class SourcePublicApiContractTests(SourceWorkflowFixture):
    def test_invalid_and_unknown_pins_fail_closed_with_public_error_envelopes(self):
        invalid = ("", "x" * 65, 42, [])
        for version in invalid:
            with self.subTest(version=repr(version)):
                catalog = search_catalog(query="Takamine", snapshot_version=version)
                policy = lookup_public_policy(query="horário", snapshot_version=version)
                self.assertEqual((catalog["outcome"], catalog["error_category"]), ("error", "invalid_arguments"))
                self.assertEqual((policy["outcome"], policy["error_category"]), ("error", "invalid_arguments"))
        missing = self._pinned_results("missing-version")
        self.assertTrue(all(item["error_category"] == "source_unavailable" for item in missing))

    def test_missing_active_snapshot_database_error_and_bad_pdf_are_unavailable(self):
        SourceSnapshot.objects.update(is_active=False)
        self.assertTrue(all(item["error_category"] == "source_unavailable" for item in self._active_results()))
        with patch("emporio.catalog.services.SourceSnapshot.objects.filter", side_effect=DatabaseError):
            self.assertEqual(search_catalog(query="x")["error_category"], "source_unavailable")
        with patch("emporio.policy.verify_snapshot_pdf", side_effect=SourceImportError("bad hash")):
            self.assertEqual(lookup_public_policy(query="hours")["error_category"], "source_unavailable")

    def test_policy_page_range_and_tied_locators_are_stable_and_versioned(self):
        snapshot = self.snapshot
        snapshot.manifest["policy"]["passages"] = [
            self._passage(4, "§4", [4, 0, 999, True, 1]),
            self._passage(2, "§2", [2]),
        ]
        snapshot.save(update_fields=["manifest"])
        result = lookup_public_policy(query="locator evidence", topic="hours")
        self.assertEqual([(item["page"], item["section"]) for item in result["data"]], [(2, "§2"), (4, "§4")])
        self.assertEqual([(source["page"], source["section"]) for source in result["sources"]], [(2, "§2"), (4, "§4"), (4, "§4"), (1, "§4")])
        self.assertTrue(all(source["bundle_version"] == snapshot.version for source in result["sources"]))

    def _active_results(self):
        return [search_catalog(query="x"), lookup_public_policy(query="hours")]

    def _pinned_results(self, version):
        return [
            search_catalog(query="x", snapshot_version=version),
            lookup_public_policy(query="hours", snapshot_version=version),
        ]

    def _passage(self, page, section, pages):
        return {"audience": "public", "topic": "hours", "text": "locator evidence",
                "page": page, "pages": pages, "section": section, "conflict": False}
