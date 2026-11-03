from datetime import timedelta
from unittest.mock import Mock

from django.test import TestCase
from django.utils import timezone

from emporio.agent_protocol import FAILURE_TEXT
from emporio.chat.models import Conversation, IncomingMessage, OutgoingReply
from emporio.chat.worker import process_next


class ExpiredNotificationContractTests(TestCase):
    def setUp(self):
        now = timezone.now()
        self.deadline = now - timedelta(seconds=10)
        conversation = Conversation.objects.create(sender="15551234567", last_customer_at=now)
        self.job = IncomingMessage.objects.create(
            conversation=conversation, provider_id="wamid.expired", sender=conversation.sender,
            text="Uma pergunta antiga", state="pending", received_at=now - timedelta(minutes=2),
            occurred_at=now - timedelta(minutes=2), deadline=self.deadline,
            snapshot_version="snapshot-a",
        )

    def test_expired_turn_records_and_sends_one_fixed_notice_while_window_is_open(self):
        model, send = Mock(), Mock(return_value="wamid.notice")
        first = process_next(model_client=model, send_client=send)
        self.job.refresh_from_db()
        self.assertEqual((first.state, self.job.state), ("notification_pending", "notification_pending"))
        self.assertEqual(first.text, FAILURE_TEXT)
        self.assertEqual(self.job.deadline, self.deadline)
        self.assertFalse(model.called)
        self.assertFalse(send.called)

        second = process_next(model_client=model, send_client=send)
        self.assertEqual(second.state, "accepted")
        self.assertEqual(second.text, FAILURE_TEXT)
        self.assertEqual(send.call_count, 1)
        self.assertEqual(model.call_count, 0)
        self.assertEqual(second.source.deadline, self.deadline)
