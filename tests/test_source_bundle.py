import hashlib
import shutil
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase, override_settings

from emporio.catalog.models import SourceSnapshot

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
CSV_NAMES = (
    "categories",
    "customers",
    "order_items",
    "orders",
    "products",
    "promotions",
)


class SourceBundleTests(TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.bundle_root = Path(self.temporary.name) / "bundles"
        self.source_dir = Path(self.temporary.name) / "sources"
        shutil.copytree(DATA_DIR, self.source_dir)

    def import_sources(self):
        with override_settings(EMPORIO_BUNDLE_ROOT=str(self.bundle_root)):
            call_command("load_sources", source_dir=str(self.source_dir), verbosity=0)
        return SourceSnapshot.objects.get(is_active=True)

    def assert_manifest_hashes(self, snapshot, bundle):
        for name in CSV_NAMES:
            path = bundle / f"desafio_tecnico_ai_eng - {name}.csv"
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(),
                snapshot.manifest["csv_sha256"][name],
            )

    def test_import_retains_immutable_source_bundle_and_manifest_hashes(self):
        first = self.import_sources()
        bundle = self.bundle_root / first.version

        self.assertTrue(bundle.is_dir())
        expected_files = {f"desafio_tecnico_ai_eng - {name}.csv" for name in CSV_NAMES}
        expected_files.add("políticas_da_loja.pdf")
        self.assertEqual({path.name for path in bundle.iterdir()}, expected_files)
        self.assert_manifest_hashes(first, bundle)
        self.assertEqual(
            (bundle / "políticas_da_loja.pdf").read_bytes(),
            (self.source_dir / "políticas_da_loja.pdf").read_bytes(),
        )

        old_bytes = {path.name: path.read_bytes() for path in bundle.iterdir()}
        product_csv = self.source_dir / "desafio_tecnico_ai_eng - products.csv"
        product_csv.write_bytes(product_csv.read_bytes() + b"\n")
        second = self.import_sources()

        self.assertNotEqual(first.version, second.version)
        self.assertEqual(old_bytes, {path.name: path.read_bytes() for path in bundle.iterdir()})
