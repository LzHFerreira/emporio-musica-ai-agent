from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from emporio.catalog import search_catalog
from emporio.models import Order
from tests.source_csv_fixtures import copy_sources, edit_first_row, source_file

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


class SourceValidationTests(TestCase):
    def setUp(self):
        call_command("load_sources", source_dir=str(DATA_DIR), verbosity=0)

    def active_version(self):
        return search_catalog(query="Takamine GD20", mode="resolve")["sources"][0]["bundle_version"]

    def assert_rejected_without_activation(self, source_dir, version):
        with self.assertRaises(CommandError):
            call_command("load_sources", source_dir=str(source_dir), verbosity=0)
        self.assertEqual(self.active_version(), version)

    def test_invalid_foreign_keys_duplicate_keys_and_integer_boolean_fail(self):
        version = self.active_version()
        invalid = (("promotions", "product_id", "999999", False), ("orders", "customer_id", "999999", False), ("order_items", "order_id", "999999", False), ("order_items", "product_id", "999999", False), ("order_items", "quantity", "true", False), ("categories", "category_id", "1", True), ("products", "product_id", "1", True), ("promotions", "promotion_id", "1", True), ("customers", "customer_id", "1", True), ("orders", "order_id", "1", True), ("order_items", "order_id", "1", True))
        for name, field, value, duplicate in invalid:
            with self.subTest(source=name, field=field, duplicate=duplicate):
                source_dir = copy_sources(self)
                edit_first_row(source_dir, name, field, value, duplicate)
                self.assert_rejected_without_activation(source_dir, version)

    def test_promotion_percent_flags_and_order_dates_are_strict(self):
        version = self.active_version()
        invalid = (("promotions", "discount_percent", "NaN"), ("promotions", "discount_percent", "100.01"), ("promotions", "discount_percent", "10.001"), ("promotions", "is_active", "yes"), ("orders", "order_date", "not-a-date"))
        for name, field, value in invalid:
            with self.subTest(source=name, field=field, value=value):
                source_dir = copy_sources(self)
                edit_first_row(source_dir, name, field, value)
                self.assert_rejected_without_activation(source_dir, version)

    def test_blank_optional_delivery_date_imports_as_null(self):
        source_dir = copy_sources(self)
        edit_first_row(source_dir, "orders", "estimated_delivery", "")
        call_command("load_sources", source_dir=str(source_dir), verbosity=0)
        self.assertTrue(Order.objects.filter(snapshot__is_active=True, estimated_delivery__isnull=True).exists())

    def test_csv_schema_encoding_and_row_shape_are_strict(self):
        version = self.active_version()
        for case in ("header", "encoding", "short_row"):
            with self.subTest(case=case):
                source_dir = copy_sources(self)
                path = source_file(source_dir, "products")
                if case == "header":
                    path.write_text(path.read_text(encoding="utf-8-sig").replace("product_id,", "product-id,", 1), encoding="utf-8-sig")
                elif case == "encoding":
                    path.write_bytes(b"\xff")
                else:
                    with path.open("a", encoding="utf-8", newline="") as stream:
                        stream.write("\n999,short")
                self.assert_rejected_without_activation(source_dir, version)

    def test_source_file_size_and_row_count_limits_are_enforced(self):
        version = self.active_version()
        for name, large_file in (("products", True), ("categories", False)):
            with self.subTest(source=name):
                source_dir = copy_sources(self)
                path = source_file(source_dir, name)
                if large_file:
                    with path.open("ab") as stream:
                        stream.write(b"x" * (2 * 1024 * 1024))
                else:
                    path.write_text("category_id,name,description\n" + "1,Name,Description\n" * 10_001, encoding="utf-8")
                self.assert_rejected_without_activation(source_dir, version)

    def test_source_symlink_cannot_escape_the_selected_directory(self):
        source_dir = copy_sources(self)
        product = source_file(source_dir, "products")
        outside = source_dir.parent / "outside.csv"
        outside.write_bytes(product.read_bytes())
        product.unlink()
        product.symlink_to(outside)
        self.assert_rejected_without_activation(source_dir, self.active_version())
