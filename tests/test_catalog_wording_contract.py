from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from emporio.catalog import search_catalog

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def _names(**arguments):
    return [row["name"] for row in search_catalog(**arguments)["data"]]


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
