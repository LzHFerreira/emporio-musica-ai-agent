from datetime import UTC, datetime, timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from emporio.chat.delivery import record_status, reconcile_reply
from emporio.chat.models import Conversation, DeliveryEvent, IncomingMessage, OutgoingReply


@override_settings(META_PHONE_NUMBER_ID="phone-test")
class DeliveryContractTests(TestCase):
    def setUp(self):
        self.sender = "15551234567"
        self.reply = self.make_reply()

    def make_reply(self):
        now = timezone.now()
        conversation = Conversation.objects.create(sender=self.sender)
        source = IncomingMessage.objects.create(
            conversation=conversation, provider_id="incoming-1", sender=self.sender,
            text="status?", received_at=now, occurred_at=now,
            deadline=now + timedelta(minutes=1), snapshot_version="snapshot-a",
        )
        return OutgoingReply.objects.create(source=source, text="sent", state="accepted", provider_id="wamid-1")

    def status(self, state, *, recipient=None, timestamp=None, provider_id="wamid-1"):
        occurred = timestamp or int(timezone.now().timestamp())
        return {"id": provider_id, "recipient_id": recipient or self.sender,
                "status": state, "timestamp": str(occurred)}

    def record(self, status, phone="phone-test"):
        record_status(status, phone)
        self.reply.refresh_from_db()

    def test_wrong_recipient_and_wrong_phone_cannot_advance_delivery(self):
        self.record(self.status("delivered", recipient="15557654321"))
        self.record(self.status("read"), phone="another-phone")
        self.assertEqual((self.reply.state, self.reply.delivery_at), ("accepted", None))

    def test_delivery_state_advances_monotonically_and_ignores_older_callback(self):
        delivered = int((timezone.now() - timedelta(seconds=5)).timestamp())
        self.record(self.status("delivered", timestamp=delivered))
        self.record(self.status("read", timestamp=delivered + 1))
        self.record(self.status("sent", timestamp=delivered - 1))
        self.assertEqual(self.reply.state, "read")
        self.assertEqual(int(self.reply.delivery_at.timestamp()), delivered + 1)

    def test_failure_cannot_regress_already_delivered_reply(self):
        self.record(self.status("delivered"))
        self.record(self.status("failed"))
        self.assertEqual(self.reply.state, "delivered")

    def test_early_status_is_scoped_deduplicated_and_reconciled(self):
        early = self.status("delivered", provider_id="wamid-later")
        record_status(early, "phone-test")
        record_status(early, "phone-test")
        self.assertEqual(DeliveryEvent.objects.count(), 1)
        self.reply.provider_id = "wamid-later"
        self.reply.save(update_fields=["provider_id"])
        reconcile_reply(self.reply, "phone-test")
        self.reply.refresh_from_db()
        self.assertEqual(self.reply.state, "delivered")
        self.assertFalse(DeliveryEvent.objects.exists())

    def test_malformed_or_future_status_is_ignored(self):
        invalid = [None, [], self.status("queued"), self.status("read", recipient="bad"),
                   self.status("read", timestamp=int((timezone.now() + timedelta(hours=1)).timestamp()))]
        for status in invalid:
            record_status(status, "phone-test")
        self.reply.refresh_from_db()
        self.assertEqual(self.reply.state, "accepted")
        self.assertEqual(DeliveryEvent.objects.count(), 0)

    def test_expired_unmatched_event_is_removed_before_capacity_check(self):
        event = DeliveryEvent.objects.create(
            phone_number_id="phone-test", provider_id="old", recipient_id=self.sender,
            status="sent", occurred_at=datetime.now(UTC),
        )
        DeliveryEvent.objects.filter(pk=event.pk).update(received_at=timezone.now() - timedelta(hours=25))
        record_status(self.status("sent", provider_id="unmatched"), "phone-test")
        self.assertEqual(list(DeliveryEvent.objects.values_list("provider_id", flat=True)), ["unmatched"])
