from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.db import DatabaseError
from django.test import TestCase

from emporio.catalog.models import SourceSnapshot
from emporio.orders.models import Customer
from emporio.orders_access import get_own_order_status, list_own_orders, sender_binding

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


class OrderOwnershipContractTests(TestCase):
    def setUp(self):
        call_command("load_sources", source_dir=str(DATA_DIR), verbosity=0)
        self.snapshot = SourceSnapshot.objects.get(is_active=True)

    def test_authenticated_sender_matches_normalized_phone_and_sees_own_order(self):
        result = get_own_order_status("5567998123456", order_id=4, snapshot_version=self.snapshot.version)
        self.assertEqual((result["outcome"], result["data"][0]["order_id"]), ("found", 4))
        self.assertEqual(set(result["data"][0]), {"order_id", "status", "tracking_code", "estimated_delivery"})
        orders = list_own_orders("5567998123456", page=1, snapshot_version=self.snapshot.version)
        self.assertEqual(orders["outcome"], "found")
        self.assertEqual(set(orders["data"][0]), {"order_id", "order_date", "status"})

    def test_other_customer_cannot_read_order_by_numeric_id(self):
        result = get_own_order_status("55679996547821", order_id=4, snapshot_version=self.snapshot.version)
        self.assertEqual((result["outcome"], result["data"]), ("denied", []))
        self.assertNotIn("tracking_code", str(result))

    def test_duplicate_normalized_phone_match_denies_restricted_access(self):
        first = Customer.objects.get(snapshot=self.snapshot, source_id=1)
        second = Customer.objects.get(snapshot=self.snapshot, source_id=2)
        Customer.objects.filter(pk=second.pk).update(phone="0055 67 99812-3456")
        result = list_own_orders("5567998123456", page=1, snapshot_version=self.snapshot.version)
        self.assertEqual((result["outcome"], result["data"]), ("denied", []))

    def test_invalid_sender_page_id_unknown_snapshot_and_missing_order_fail_closed(self):
        denied = (
            list_own_orders("not-a-phone", page=1, snapshot_version=self.snapshot.version),
            list_own_orders("5567998123456", page=True, snapshot_version=self.snapshot.version),
            get_own_order_status("5567998123456", order_id=True, snapshot_version=self.snapshot.version),
            get_own_order_status("5567998123456", order_id=999, snapshot_version=self.snapshot.version),
            list_own_orders("5567998123456", page=1, snapshot_version="missing-version"),
        )
        self.assertTrue(all(item["outcome"] == "denied" and item["data"] == [] for item in denied))
        self.assertEqual(list_own_orders("5567998123456", page=2, snapshot_version=self.snapshot.version)["outcome"], "not_found")

    def test_binding_returns_only_unique_internal_match_and_hides_storage_errors(self):
        self.assertTrue(sender_binding("5567998123456", self.snapshot.version))
        self.assertEqual(sender_binding("5555555555555", self.snapshot.version), "")
        with patch("emporio.orders_access.SourceSnapshot.objects.all", side_effect=DatabaseError("locked")):
            self.assertEqual(sender_binding("5567998123456", self.snapshot.version), "")
            result = list_own_orders("5567998123456", page=1, snapshot_version=self.snapshot.version)
        self.assertEqual(result["outcome"], "denied")
