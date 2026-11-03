import csv
import json
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from emporio.catalog import search_catalog
from tests.source_csv_fixtures import copy_sources, source_file

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SPEC_KEYS = ("top", "back_sides", "neck", "strings", "scale", "electronics", "color", "body", "shells", "pieces", "hardware", "keys", "type", "polyphony")


def load_worst_case_catalog(test_case):
    source_dir = copy_sources(test_case)
    path = source_file(source_dir, "products")
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields, rows = reader.fieldnames, list(reader)
    for row in rows:
        if row["category_id"] == "5":
            row["description"] = "🎸" * 600
            row["specs"] = json.dumps({key: "🎸" * 80 for key in SPEC_KEYS}, ensure_ascii=False)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    call_command("load_sources", source_dir=str(source_dir), verbosity=0)


class ProjectionSizeTests(TestCase):
    def setUp(self):
        call_command("load_sources", source_dir=str(DATA_DIR), verbosity=0)

    def test_serialized_catalog_result_stays_within_12_kib(self):
        load_worst_case_catalog(self)
        result = search_catalog(query="", mode="search", category="Violões")
        encoded = json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.assertLessEqual(len(encoded), 12 * 1024)
        self.assertEqual(result["sources"][0]["type"], "catalog")
        self.assertTrue(result["sources"][0]["bundle_version"])
        self.assertEqual(len(result["data"]), 5)
        for item in result["data"]:
            self.assertTrue(item["name"] and item["base_price_brl"] and item["payable_price_brl"] and item["availability"])
            self.assertTrue(item["truncated_fields"])
