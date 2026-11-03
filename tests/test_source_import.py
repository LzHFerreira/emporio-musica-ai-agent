import csv
import shutil
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from emporio.catalog import search_catalog
from emporio.models import Category, Customer, Order, OrderItem, Product, Promotion

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
PRODUCT_NAME = "Crafter HT-100 Folk Aço Natural"


class SourceImportTests(TestCase):
    def setUp(self):
        call_command("load_sources", source_dir=str(DATA_DIR), verbosity=0)

    def copy_sources(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        destination = Path(temporary.name) / "data"
        shutil.copytree(DATA_DIR, destination)
        return destination

    def change_product(self, source_dir, name, column, value):
        path = source_dir / "desafio_tecnico_ai_eng - products.csv"
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            fields, rows = reader.fieldnames, list(reader)
        row = next(item for item in rows if item["name"] == name)
        row[column] = value
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    def product_id(self, source_dir, name):
        path = source_dir / "desafio_tecnico_ai_eng - products.csv"
        with path.open(encoding="utf-8-sig", newline="") as stream:
            return next(row["product_id"] for row in csv.DictReader(stream) if row["name"] == name)

    def append_promotion(self, source_dir, product_id):
        path = source_dir / "desafio_tecnico_ai_eng - promotions.csv"
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            fields, rows = reader.fieldnames, list(reader)
        rows.append({"promotion_id": "999999", "product_id": product_id, "discount_percent": "10", "description": "Second active offer", "is_active": "1"})
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    def test_unchanged_import_is_idempotent(self):
        before = search_catalog(query="Takamine GD20", mode="resolve")
        models = (Category, Product, Promotion, Customer, Order, OrderItem)
        counts = tuple(model.objects.count() for model in models)
        self.assertTrue(all(counts))
        call_command("load_sources", source_dir=str(DATA_DIR), verbosity=0)
        after = search_catalog(query="Takamine GD20", mode="resolve")
        self.assertEqual(before["sources"][0]["bundle_version"], after["sources"][0]["bundle_version"])
        self.assertEqual(before["data"], after["data"])
        self.assertEqual(counts, tuple(model.objects.count() for model in models))
        self.assertEqual(len(after["data"]), 1)

    def test_invalid_public_rows_roll_back_the_active_snapshot(self):
        before = search_catalog(query="Takamine GD20", mode="resolve")
        invalid = (("category_id", "999999"), ("price_brl", "not-money"), ("price_brl", "NaN"), ("price_brl", "-1"), ("price_brl", "1.001"), ("status", "unknown"), ("stock_quantity", "-1"), ("stock_quantity", "true"), ("specs", "{invalid-json"), ("specs", '{"unknown":"value"}'), ("specs", '{"strings":7}'))
        for column, value in invalid:
            with self.subTest(column=column):
                source_dir = self.copy_sources()
                self.change_product(source_dir, "Giannini GN-15 Nylon Cedr Natural", column, value)
                with self.assertRaises(CommandError):
                    call_command("load_sources", source_dir=str(source_dir), verbosity=0)
                after = search_catalog(query="Takamine GD20", mode="resolve")
                self.assertEqual(after["sources"][0]["bundle_version"], before["sources"][0]["bundle_version"])

    def test_pix_uses_decimal_half_up_rounding(self):
        source_dir = self.copy_sources()
        name = "Tagima Memphis AC-39 Nylon Natural"
        self.change_product(source_dir, name, "price_brl", "199.90")
        call_command("load_sources", source_dir=str(source_dir), verbosity=0)
        result = search_catalog(query=name, mode="resolve", payment_method="pix", max_price_brl="189.91")
        item = result["data"][0]
        self.assertEqual((item["base_price_brl"], item["payable_price_brl"]), ("199.90", "189.91"))

    def test_extreme_money_is_a_bounded_import_error_and_rolls_back(self):
        before = search_catalog(query="Takamine GD20", mode="resolve")
        source_dir = self.copy_sources()
        self.change_product(source_dir, "Giannini GN-15 Nylon Cedr Natural", "price_brl", "9" * 40)
        with self.assertRaises(CommandError):
            call_command("load_sources", source_dir=str(source_dir), verbosity=0)
        after = search_catalog(query="Takamine GD20", mode="resolve")
        self.assertEqual(before["sources"][0]["bundle_version"], after["sources"][0]["bundle_version"])

    def test_pricing_rule_revision_versions_the_derived_snapshot(self):
        before = search_catalog(query="Giannini GNF-3", mode="resolve", payment_method="pix")
        with override_settings(EMPORIO_PIX_BASIS_POINTS=300, EMPORIO_PRICING_RULE_VERSION="pix-300-v1"):
            call_command("load_sources", source_dir=str(DATA_DIR), verbosity=0)
            changed = search_catalog(query="Giannini GNF-3", mode="resolve", payment_method="pix")
            excluded = search_catalog(query="Giannini GNF-3", mode="resolve", payment_method="pix", max_price_brl="1000")["data"]
            call_command("load_sources", source_dir=str(DATA_DIR), verbosity=0)
            repeated = search_catalog(query="Giannini GNF-3", mode="resolve", payment_method="pix")
        self.assertNotEqual(before["sources"][0]["bundle_version"], changed["sources"][0]["bundle_version"])
        self.assertEqual(changed["data"][0]["payable_price_brl"], "1017.53")
        self.assertEqual(excluded, [])
        self.assertEqual(changed["sources"][0]["bundle_version"], repeated["sources"][0]["bundle_version"])

    def test_multiple_active_promotions_are_ambiguous_and_not_stacked(self):
        source_dir = self.copy_sources()
        product_id = self.product_id(source_dir, PRODUCT_NAME)
        self.append_promotion(source_dir, product_id)
        call_command("load_sources", source_dir=str(source_dir), verbosity=0)
        item = search_catalog(query="Crafter HT-100", mode="resolve", payment_method="pix")["data"][0]
        self.assertEqual(item["promotion"]["state"], "ambiguous")
        self.assertEqual(item["payable_price_brl"], "2399.00")
