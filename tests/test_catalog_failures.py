from pathlib import Path

from django.core.management import call_command
from django.db import DatabaseError, connection
from django.test import TestCase

from emporio.catalog import search_catalog
from emporio.catalog.models import SourceSnapshot

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


class CatalogFailureTests(TestCase):
    def setUp(self):
        call_command("load_sources", source_dir=str(DATA_DIR), verbosity=0)

    def test_missing_active_snapshot_is_unavailable_not_empty(self):
        SourceSnapshot.objects.update(is_active=False)
        result = search_catalog(query="Takamine GD20")
        self.assertEqual((result["outcome"], result["error_category"], result["data"], result["sources"]), ("error", "source_unavailable", [], []))

    def test_page_beyond_matching_rows_is_not_found(self):
        result = search_catalog(query="Takamine GD20", mode="resolve", page=2)
        self.assertEqual((result["outcome"], result["data"], result["sources"], result["page"], result["has_more"]), ("not_found", [], [], None, False))

    def test_database_read_error_is_bounded_as_source_unavailable(self):
        def fail_read(execute, sql, params, many, context):
            raise DatabaseError("synthetic database read error")

        with connection.execute_wrapper(fail_read):
            result = search_catalog(query="Takamine GD20")
        self.assertEqual((result["outcome"], result["error_category"], result["data"], result["sources"]), ("error", "source_unavailable", [], []))
