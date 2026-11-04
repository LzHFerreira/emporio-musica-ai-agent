from pathlib import Path

from django.core.management import call_command
from django.db import connection
from django.test import TestCase

from emporio.catalog import search_catalog
from emporio.catalog.models import Product

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


class PublicCatalogTests(TestCase):
    def setUp(self):
        call_command("load_sources", source_dir=str(DATA_DIR), verbosity=0)

    def lookup(self, query, **arguments):
        arguments.setdefault("mode", "resolve")
        arguments.setdefault("payment_method", "unspecified")
        arguments.setdefault("available_only", False)
        return search_catalog(query=query, **arguments)

    def test_pix_budget_boundary_and_public_projection(self):
        found = self.lookup("Giannini GNF-3", payment_method="pix", available_only=True, max_price_brl="996.55")
        self.assertEqual(set(found), {"outcome", "data", "sources", "page", "pagination_restarted", "has_more", "error_category"})
        self.assertEqual(found["sources"][0]["type"], "catalog")
        self.assertTrue(found["sources"][0]["bundle_version"])
        self.assertIn(("policy", 3, "§3"), {(source["type"], source["page"], source["section"]) for source in found["sources"]})
        item = found["data"][0]
        self.assertEqual(set(item), {"name", "description", "category", "specs", "base_price_brl", "payable_price_brl", "payment_condition", "availability", "promotion", "truncated_fields"})
        self.assertEqual((item["name"], item["base_price_brl"], item["payable_price_brl"], item["availability"]), ("Giannini GNF-3 CEQ Elétrico Nylon Natural", "1049.00", "996.55", "available"))
        self.assertNotIn("product_id", item)
        self.assertNotIn("stock_quantity", item)
        self.assertEqual(self.lookup("Giannini GNF-3", payment_method="pix", available_only=True, max_price_brl="996.54")["data"], [])
        self.assertEqual(self.lookup("Giannini GNF-3", payment_method="credit", available_only=True, max_price_brl="1000")["data"], [])

    def test_budget_and_availability_filter_before_pagination(self):
        page = self.lookup("", mode="search", category="Violões", payment_method="credit", available_only=True, max_price_brl="899", page=2)
        self.assertEqual((page["page"], len(page["data"]), page["has_more"]), (2, 5, True))
        self.assertIn("Yamaha C70 Nylon Natural", {item["name"] for item in page["data"]})
        last = self.lookup("", mode="search", category="Violões", payment_method="credit", available_only=True, max_price_brl="899", page=3)
        self.assertEqual((len(last["data"]), last["has_more"]), (1, False))

    def test_availability_uses_status_and_stock_without_disclosure(self):
        cases = (("Giannini GF-3D Dreadnought Sunburst", "temporarily_unavailable"), ("Kala KA-ABP-CTG Barítono Cedar", "coming_soon"), ("Ibanez Bass 2X Electric Bass", "discontinued"))
        for name, expected in cases:
            with self.subTest(name=name):
                item = self.lookup(name)["data"][0]
                self.assertEqual(item["availability"], expected)
                self.assertNotIn("stock_quantity", item)
                self.assertNotIn("product_id", item)

    def test_active_promotion_is_not_stacked_with_pix(self):
        result = self.lookup("Crafter HT-100", payment_method="pix")
        item = result["data"][0]
        self.assertEqual((item["base_price_brl"], item["payable_price_brl"]), ("2399.00", "1967.18"))
        self.assertIn(("policy", 6, "§6.2"), {(source["type"], source["page"], source["section"]) for source in result["sources"]})

    def test_inactive_promotion_does_not_change_the_payable_price(self):
        item = self.lookup("Takamine GD20")["data"][0]
        self.assertEqual((item["base_price_brl"], item["payable_price_brl"]), ("2199.00", "2199.00"))
        self.assertIsNone(item["promotion"]["discount_percent"])

    def test_ambiguous_name_returns_candidates_not_a_silent_choice(self):
        result = self.lookup("Yamaha")
        self.assertEqual(result["outcome"], "ambiguous")
        self.assertGreater(len(result["data"]), 1)
        self.assertTrue(all("product_id" not in item for item in result["data"]))

    def test_search_normalizes_accents_and_case(self):
        result = self.lookup("VIOLAO NYLON", mode="search", category="violoes", available_only=True)
        self.assertIn("Tagima Memphis AC-39 Nylon Natural", {item["name"] for item in result["data"]})

    def test_de_article_does_not_drop_nylon_guitars(self):
        def names(query):
            result = self.lookup(query, mode="search", category="Violões", available_only=True, payment_method="pix", max_price_brl="1000")
            return {item["name"] for item in result["data"]}
        self.assertEqual(names("violão de nylon"), names("violao nylon"))
        self.assertIn("Yamaha C40 Nylon Natural", names("violão de nylon"))
        self.assertIn("Giannini GN-15 Nylon Cedr Natural", names("violão de nylon"))

    def test_search_tokens_include_the_product_category(self):
        result = self.lookup("guitarras", mode="search")
        self.assertTrue(result["data"])
        self.assertTrue(all(item["category"] == "Guitarras" for item in result["data"]))

    def test_search_uses_whole_tokens(self):
        self.assertEqual(self.lookup("kamine")["data"], [])

    def test_underscore_is_a_punctuation_separator_for_model_codes(self):
        self.assertEqual(self.lookup("AC_39")["data"][0]["name"], "Tagima Memphis AC-39 Nylon Natural")

    def test_explicit_card_payment_is_not_reported_as_unspecified(self):
        item = self.lookup("Tagima Memphis AC-39", payment_method="credit")["data"][0]
        self.assertIn("crédito", item["payment_condition"].casefold())
        self.assertNotIn("não informada", item["payment_condition"].casefold())

    def test_unrecognized_read_time_status_is_unknown_and_not_sellable(self):
        name = "Takamine GD20 Dreadnought Natural"
        product = Product.objects.get(snapshot__is_active=True, name=name)
        Product.objects.filter(pk=product.pk).update(status="legacy_unknown")
        self.assertEqual(self.lookup(name)["data"][0]["availability"], "unknown")
        self.assertEqual(self.lookup(name, available_only=True)["data"], [])

    def test_noninteger_read_time_stock_is_unknown_and_not_sellable(self):
        name = "Takamine GD20 Dreadnought Natural"
        product = Product.objects.get(snapshot__is_active=True, name=name)
        table = connection.ops.quote_name(Product._meta.db_table)
        with connection.cursor() as cursor:
            cursor.execute(f"UPDATE {table} SET stock_quantity = %s WHERE id = %s", [0.5, product.pk])
        self.assertEqual(self.lookup(name)["data"][0]["availability"], "unknown")
        self.assertEqual(self.lookup(name, available_only=True)["data"], [])

    def test_numeric_references_are_not_resolved_as_internal_ids(self):
        self.assertEqual(self.lookup("101")["data"], [])
        self.assertEqual(self.lookup("produto 101")["data"], [])

    def test_invalid_arguments_are_rejected_without_coercion(self):
        invalid = (
            {"query": 42}, {"query": "x" * 161}, {"mode": "resolve-ish"},
            {"category": 7}, {"category": ""}, {"category": "x" * 81},
            {"max_price_brl": 1000}, {"max_price_brl": "1000.999"},
            {"payment_method": "cash"}, {"available_only": 1},
            {"page": True}, {"page": 0}, {"page": 21}, {"unexpected": "value"},
        )
        for arguments in invalid:
            with self.subTest(arguments=arguments):
                result = search_catalog(**{"query": "Takamine", **arguments})
                self.assertEqual((result["outcome"], result["error_category"]), ("error", "invalid_arguments"))
