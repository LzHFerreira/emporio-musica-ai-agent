from decimal import Decimal
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from emporio.catalog import search_catalog

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def _names(**arguments):
    return [row["name"] for row in search_catalog(**arguments)["data"]]


def _all_rows(**arguments):
    rows, page = [], 1
    while page:
        result = search_catalog(page=page, **arguments)
        rows += result["data"]
        page = page + 1 if result["has_more"] else None
    return rows


class CatalogWordingContractTests(TestCase):
    def setUp(self):
        call_command("load_sources", source_dir=str(DATA_DIR), verbosity=0)

    def test_nylon_query_without_accents_finds_yamaha_c40(self):
        names = _names(query="violao nylon", max_price_brl="1000",
                       payment_method="pix", available_only=True)
        self.assertIn("Yamaha C40 Nylon Natural", names)

    def test_model_code_without_hyphen_finds_giannini_gf3d(self):
        names = _names(query="GF3D")
        self.assertIn("Giannini GF-3D Dreadnought Sunburst", names)

    def test_beginner_wording_with_inflection_finds_yamaha_c40(self):
        names = _names(query="um violão pra iniciante")
        self.assertIn("Yamaha C40 Nylon Natural", names)

    def test_budget_sentence_with_pix_returns_violoes_within_budget(self):
        rows = search_catalog(query="violão até 800 reais no pix", max_price_brl="800",
                              payment_method="pix", available_only=True)["data"]
        self.assertTrue(any("viol" in f"{r['name']} {r['category']}".lower() for r in rows))
        for row in rows:
            self.assertLessEqual(Decimal(row["payable_price_brl"]), Decimal("800"))
            self.assertEqual(row["availability"], "available")

    def test_violao_query_excludes_description_only_ukulele(self):
        self.assertNotIn("Ukuleles", [row["category"] for row in _all_rows(query="violão")])

    def test_ukulele_query_still_finds_kala_ka_b_baritono(self):
        rows = _all_rows(query="ukulele")
        self.assertIn("Kala KA-B Barítono Mogno", [row["name"] for row in rows])

    def test_description_only_word_still_finds_kala_ka_b_baritono(self):
        rows = _all_rows(query="ponte")
        self.assertIn("Kala KA-B Barítono Mogno", [row["name"] for row in rows])
