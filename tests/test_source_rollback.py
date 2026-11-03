from django.core.exceptions import PermissionDenied
from django.test import override_settings

from emporio.catalog.models import SourceSnapshot
from emporio.sources.drafts import rollback_sources
from tests.test_source_bulk_fixture import SourceBulkFixture


class SourceRollbackTests(SourceBulkFixture):
    def test_rollback_requires_independent_permission(self):
        original, _, _, changed = self.published_price_change()
        with self.assertRaises(PermissionDenied):
            rollback_sources(
                self.user, original.version, expected_version=changed.version, reason="restore"
            )

    def test_verified_rollback_restores_catalog_pricing(self):
        original, product, original_prices, changed = self.published_price_change()
        self.grant(self.user, "rollback_sources", "edit_products", "publish_products")
        restored = rollback_sources(
            self.user, original.version, expected_version=changed.version, reason="restore"
        )
        self.assertTrue(restored.is_active)
        product.refresh_from_db()
        prices = (product.base_cents, product.standard_payable_cents, product.pix_payable_cents)
        self.assertEqual(prices, original_prices)

    def test_rollback_rejects_stale_target_hash_and_incompatible_rule(self):

        active = SourceSnapshot.objects.get(is_active=True)
        self.grant(self.user, "rollback_sources", "edit_products", "publish_products")
        bundle = self.bundle_root / active.version
        source = next(bundle.glob("*products.csv"))
        source.write_bytes(source.read_bytes() + b"tampered")
        with self.assertRaises(Exception):
            rollback_sources(self.user, active.version, expected_version="stale", reason="stale")
        with self.assertRaises(Exception):
            rollback_sources(
                self.user, active.version, expected_version=active.version, reason="tampered"
            )
        source.write_bytes(source.read_bytes().removesuffix(b"tampered"))
        with override_settings(EMPORIO_PRICING_RULE_VERSION="unreviewed-rule"):
            with self.assertRaises(Exception):
                rollback_sources(
                    self.user,
                    active.version,
                    expected_version=active.version,
                    reason="rule mismatch",
                )
